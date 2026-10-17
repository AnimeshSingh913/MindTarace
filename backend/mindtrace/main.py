"""FastAPI application. Run with:  uvicorn mindtrace.main:app --reload --port 8000"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from mindtrace import __version__, pipeline
from mindtrace.config import Settings, get_settings
from mindtrace.llm import LLMClient, LLMError, LLMUnavailable, MockLLMClient, OllamaClient
from mindtrace.modes import MODES
from mindtrace.parser import ParseError
from mindtrace.schemas import AnalyzeRequest, AnalyzeResponse, ModeInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mindtrace")


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.mock_llm and llm is None:
        settings = replace(settings, model="mock", judge_model="mock")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = llm or (MockLLMClient() if settings.mock_llm else OllamaClient(settings))
        app.state.llm = client
        logger.info("MindTrace %s using %s", __version__, "mock LLM" if settings.mock_llm else settings.model)
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

    @app.get("/api/health")
    async def health(client: LLMClient = Depends(get_llm)) -> dict:
        llm_status = await client.health()
        ready = llm_status.get("reachable") and llm_status.get("model_ready")
        return {"status": "ok" if ready else "degraded", "version": __version__, "llm": llm_status}

    @app.get("/api/modes", response_model=list[ModeInfo])
    async def modes() -> list[ModeInfo]:
        return [ModeInfo(key=m.key, label=m.label, fields=[f.title for f in m.fields]) for m in MODES.values()]

    @app.post("/api/analyze", response_model=AnalyzeResponse, response_model_exclude_none=True)
    async def analyze(body: AnalyzeRequest, client: LLMClient = Depends(get_llm)) -> AnalyzeResponse:
        try:
            return await pipeline.analyze(body, client, settings)
        except LLMUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (LLMError, ParseError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - never leak internals to the client
            logger.exception("Unexpected error during analysis")
            raise HTTPException(status_code=500, detail="Internal error. See server logs.") from exc

    return app


app = create_app()
