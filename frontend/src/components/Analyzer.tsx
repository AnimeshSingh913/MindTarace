import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2, Sparkles, X } from "lucide-react";
import { analyze, ApiError, type AnalyzeResponse, type Mode } from "@/lib/api";
import { EXAMPLES, MODE_INFO } from "@/lib/examples";
import { ResultPanel } from "./ResultPanel";

const MAX_CHARS = 4000;
const MODES: Mode[] = ["education", "interview", "research"];

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; result: AnalyzeResponse }
  | { kind: "error"; error: ApiError };

const Counter = ({ value }: { value: string }) => (
  <span className={`text-xs tabular-nums ${value.length > MAX_CHARS ? "text-danger" : "text-subtle"}`}>
    {value.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
  </span>
);

const LoadingSkeleton = () => (
  <div className="space-y-5" aria-label="Analysing" role="status">
    <div className="skeleton h-8 w-40" />
    <div className="grid grid-cols-3 gap-2">
      <div className="skeleton h-14" />
      <div className="skeleton h-14" />
      <div className="skeleton h-14" />
    </div>
    {[0, 1, 2].map((i) => (
      <div key={i} className="space-y-2">
        <div className="skeleton h-3 w-28" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-5/6" />
      </div>
    ))}
    <p className="text-xs text-subtle">This usually takes a few seconds.</p>
  </div>
);

export const Analyzer = () => {
  const [problem, setProblem] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [mode, setMode] = useState<Mode>("education");
  const [state, setState] = useState<State>({ kind: "idle" });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const tooLong = problem.length > MAX_CHARS || reasoning.length > MAX_CHARS;
  const canSubmit = problem.trim() !== "" && reasoning.trim() !== "" && !tooLong && state.kind !== "loading";

  const submit = async () => {
    if (!canSubmit) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setState({ kind: "loading" });
    try {
      const result = await analyze({ problem, reasoning, mode }, ctrl.signal);
      setState({ kind: "done", result });
    } catch (err) {
      if (ctrl.signal.aborted) return setState({ kind: "idle" });
      setState({ kind: "error", error: err instanceof ApiError ? err : new ApiError("server", String(err)) });
    }
  };

  const cancel = () => abortRef.current?.abort();

  const loadExample = (i: number) => {
    const ex = EXAMPLES[i];
    setProblem(ex.problem);
    setReasoning(ex.reasoning);
    setMode(ex.mode);
    setState({ kind: "idle" });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <section id="analyze" className="scroll-mt-14 border-b border-border">
      <div className="container-page py-20">
        <div className="max-w-2xl">
          <p className="eyebrow text-accent">Try it</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Analyze a reasoning mistake</h2>
          <p className="mt-2 text-subtle">
            Paste a problem and the reasoning behind a wrong answer. You'll get a structured diagnosis, never the answer.
          </p>
        </div>

        <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-5" onKeyDown={onKeyDown}>
            <div>
              <div className="mb-1.5 flex items-baseline justify-between">
                <label htmlFor="problem" className="text-sm font-medium">Problem</label>
                <Counter value={problem} />
              </div>
              <textarea
                id="problem"
                className="field min-h-[96px]"
                rows={3}
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                placeholder="e.g. A rectangle is 8 cm by 5 cm. Find its perimeter."
              />
            </div>
            <div>
              <div className="mb-1.5 flex items-baseline justify-between">
                <label htmlFor="reasoning" className="text-sm font-medium">Reasoning</label>
                <Counter value={reasoning} />
              </div>
              <textarea
                id="reasoning"
                className="field min-h-[132px]"
                rows={5}
                value={reasoning}
                onChange={(e) => setReasoning(e.target.value)}
                placeholder="Walk through how you (or a student) got there…"
              />
            </div>

            <fieldset>
              <legend className="mb-1.5 text-sm font-medium">Mode</legend>
              <div role="radiogroup" className="inline-flex rounded-lg border border-border bg-muted p-1">
                {MODES.map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={mode === m}
                    onClick={() => setMode(m)}
                    className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                      mode === m ? "bg-surface text-fg shadow-sm" : "text-subtle hover:text-fg"
                    }`}
                  >
                    {MODE_INFO[m].label}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-subtle">{MODE_INFO[mode].blurb}</p>
            </fieldset>

            <div className="flex flex-wrap items-center gap-3">
              <button type="button" className="btn-primary" onClick={submit} disabled={!canSubmit}>
                {state.kind === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {state.kind === "loading" ? "Analysing…" : "Analyze reasoning"}
              </button>
              {state.kind === "loading" && (
                <button type="button" className="btn-ghost" onClick={cancel}>
                  <X className="h-4 w-4" /> Cancel
                </button>
              )}
              <kbd className="hidden text-xs text-subtle sm:inline">Ctrl + Enter</kbd>
            </div>

            <div className="border-t border-border pt-4">
              <p className="eyebrow mb-2">Examples</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => loadExample(i)}
                    className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-subtle transition hover:border-accent/40 hover:text-fg"
                  >
                    {ex.label} <span className="text-subtle/70">· {MODE_INFO[ex.mode].label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div
            aria-live="polite"
            className="min-h-[420px] rounded-2xl border border-border bg-surface p-6 shadow-sm lg:max-h-[720px] lg:overflow-y-auto"
          >
            {state.kind === "idle" && (
              <div className="flex h-full min-h-[360px] flex-col items-center justify-center gap-2 text-center">
                <p className="text-sm font-medium">The diagnosis will appear here</p>
                <p className="max-w-xs text-xs text-subtle">Start with one of the examples if you just want to see how it works.</p>
              </div>
            )}
            {state.kind === "loading" && <LoadingSkeleton />}
            {state.kind === "done" && <ResultPanel key={state.result.meta.latency_ms} result={state.result} />}
            {state.kind === "error" && (
              <div role="alert" className="flex h-full min-h-[360px] flex-col items-center justify-center gap-3 text-center">
                <AlertTriangle className="h-6 w-6 text-danger" />
                <p className="text-sm font-semibold">
                  {state.error.kind === "validation"
                    ? "Check your input"
                    : state.error.kind === "rate_limited"
                      ? "Slow down a little"
                      : "Something went wrong"}
                </p>
                <p className="max-w-sm text-sm text-subtle">{state.error.message}</p>
                <button type="button" className="btn-ghost mt-2" onClick={submit} disabled={!canSubmit}>
                  Try again
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
