"""FastAPI application. Run with:  uvicorn mindtrace.main:app --reload --port 8000

Behind a reverse proxy (Render, Fly, nginx) run with `--proxy-headers` and the environment
variable FORWARDED_ALLOW_IPS=*, so rate limits see the real client IP rather than the proxy's.
"""

from __future__ import annotations

import logging
import math
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from mindtrace import __version__, pipeline
from mindtrace.config import Settings, get_settings
from mindtrace.llm import LLMClient, LLMError, LLMRateLimited, LLMUnavailable, build_client
from mindtrace.modes import MODES
from mindtrace.parser import ParseError
from mindtrace.ratelimit import RateLimiter
from mindtrace.schemas import AnalyzeRequest, AnalyzeResponse, ModeInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mindtrace")


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    if llm is None:
        settings.validate()
        if settings.mock_llm:
            settings = replace(settings, model="mock", judge_model="mock")
    limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_hour, settings.daily_request_cap)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = llm or build_client(settings)
        app.state.llm = client
        runtime = "mock LLM" if settings.mock_llm else f"{settings.provider}:{settings.model}"
        logger.info("MindTrace %s using %s (rate limiting %s)", __version__, runtime, "on" if limiter.enabled else "off")
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(title="MindTrace API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def get_llm(request: Request) -> LLMClient:
        return request.app.state.llm

    @app.get("/api/live")
    async def live() -> dict:
        """Liveness probe for the host: never calls the model provider."""
        return {"status": "ok"}

    @app.get("/api/health")
    async def health(client: LLMClient = Depends(get_llm)) -> dict:
        llm_status = await client.health()
        ready = llm_status.get("reachable") and llm_status.get("model_ready")
        return {"status": "ok" if ready else "degraded", "version": __version__, "llm": llm_status}

    @app.get("/api/modes", response_model=list[ModeInfo])
    async def modes() -> list[ModeInfo]:
        return [ModeInfo(key=m.key, label=m.label, fields=[f.title for f in m.fields]) for m in MODES.values()]

    @app.post("/api/analyze", response_model=AnalyzeResponse, response_model_exclude_none=True)
    async def analyze(body: AnalyzeRequest, request: Request, client: LLMClient = Depends(get_llm)) -> AnalyzeResponse:
        retry_after = limiter.check(request.client.host if request.client else "unknown")
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many analyses. Please wait a little and try again.",
                headers={"Retry-After": str(math.ceil(retry_after))},
            )
        try:
            return await pipeline.analyze(body, client, settings)
        except LLMRateLimited as exc:
            raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "30"}) from exc
        except LLMUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (LLMError, ParseError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - never leak internals to the client
            logger.exception("Unexpected error during analysis")
            raise HTTPException(status_code=500, detail="Internal error. See server logs.") from exc

    return app


app = create_app()
