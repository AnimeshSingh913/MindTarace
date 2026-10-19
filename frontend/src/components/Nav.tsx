import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/api";
import { Logo } from "./Logo";

function describe(health: Health | null | undefined): { tone: string; text: string; title: string } {
  if (health === undefined) return { tone: "bg-subtle", text: "Checking…", title: "Checking the server" };
  if (health === null) return { tone: "bg-danger", text: "Server offline", title: "The MindTrace API is not responding" };
  const { llm } = health;
  const local = llm.runtime === "ollama";
  if (llm.runtime === "mock") return { tone: "bg-warn", text: "Mock mode", title: "MINDTRACE_MOCK_LLM is on: answers are canned" };
  if (!llm.reachable)
    return { tone: "bg-danger", text: local ? "Ollama offline" : "AI offline", title: local ? "Run `ollama serve`" : "The model provider is not reachable" };
  if (!llm.model_ready)
    return { tone: "bg-warn", text: "Model missing", title: local ? `Run: ollama pull ${llm.model ?? ""}` : `Check MINDTRACE_MODEL (${llm.model ?? ""})` };
  if (!llm.judge_ready)
    return { tone: "bg-warn", text: "Judge missing", title: "Some answers may be withheld until the judge model is available" };
  return { tone: "bg-ok", text: "Ready", title: `Model ${llm.model ?? ""} ready` };
}

export const Nav = () => {
  const [health, setHealth] = useState<Health | null | undefined>(undefined);

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () => getHealth(ctrl.signal).then((h) => !ctrl.signal.aborted && setHealth(h));
    load();
    const id = setInterval(load, 30_000);
    return () => {
      ctrl.abort();
      clearInterval(id);
    };
  }, []);

  const status = describe(health);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-bg/80 backdrop-blur-md">
      <div className="container-page flex h-14 items-center justify-between">
        <a href="#top" className="flex items-center gap-2.5 font-bold tracking-tight">
          <Logo />
          <span>MindTrace</span>
        </a>
        <nav className="flex items-center gap-5 text-sm">
          <a href="#analyze" className="hidden text-subtle transition hover:text-fg sm:inline">Analyze</a>
          <a href="#modes" className="hidden text-subtle transition hover:text-fg sm:inline">Modes</a>
          <a href="#safety" className="hidden text-subtle transition hover:text-fg sm:inline">Safety</a>
          <span
            title={status.title}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-subtle"
          >
            <span className={`h-2 w-2 rounded-full ${status.tone}`} />
            {status.text}
          </span>
        </nav>
      </div>
    </header>
  );
};
