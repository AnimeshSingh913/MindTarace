export type Mode = "education" | "interview" | "research";

export interface Section {
  key: string;
  title: string;
  content: string | string[];
}

export interface AnalyzeResponse {
  mode: Mode;
  status: "ok" | "blocked";
  mistake_type?: string;
  reasoning_pattern?: string;
  confidence?: string;
  agreement?: string;
  explanation?: string;
  sections?: Section[];
  block?: { reason: string; message: string };
  meta: { model: string; latency_ms: number; judge_called: boolean; missing_fields?: string[] };
}

export interface Health {
  status: "ok" | "degraded";
  version: string;
  llm: { runtime: string; reachable: boolean; model_ready: boolean; judge_ready: boolean; model?: string };
}

export type ApiErrorKind = "network" | "timeout" | "unavailable" | "model" | "validation" | "server";

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const ANALYZE_TIMEOUT_MS = 150_000;

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : "input";
        return `${field}: ${String(d?.msg ?? "invalid").replace(/^Value error, /, "")}`;
      })
      .join("; ");
  }
  return "";
}

async function toApiError(res: Response): Promise<ApiError> {
  let detail = "";
  try {
    detail = detailText((await res.json())?.detail);
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 503) return new ApiError("unavailable", detail || "The model runtime is unavailable.", 503);
  if (res.status === 502) return new ApiError("model", detail || "The model returned an unusable response.", 502);
  if (res.status === 422) return new ApiError("validation", detail || "Please check your input.", 422);
  return new ApiError("server", detail || `Server error (${res.status}).`, res.status);
}

export async function analyze(
  body: { problem: string; reasoning: string; mode: Mode },
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), ANALYZE_TIMEOUT_MS);
  const onAbort = () => timeout.abort();
  signal?.addEventListener("abort", onAbort);
  try {
    const res = await fetch(`${BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: timeout.signal,
    });
    if (!res.ok) throw await toApiError(res);
    return (await res.json()) as AnalyzeResponse;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      if (signal?.aborted) throw err; // cancelled by the user: let the caller ignore it
      throw new ApiError("timeout", "The analysis took too long. Small local models on CPU can be slow; try again.");
    }
    throw new ApiError("network", "Can't reach the MindTrace server. Is the backend running on port 8000?");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export async function getHealth(signal?: AbortSignal): Promise<Health | null> {
  try {
    const res = await fetch(`${BASE}/api/health`, { signal });
    return res.ok ? ((await res.json()) as Health) : null;
  } catch {
    return null;
  }
}
