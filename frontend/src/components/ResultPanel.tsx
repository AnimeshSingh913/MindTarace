import { Clock, ShieldAlert, ShieldCheck } from "lucide-react";
import type { AnalyzeResponse, Section } from "@/lib/api";
import { MODE_INFO } from "@/lib/examples";

const toneFor = (value?: string) =>
  value === "Yes" || value === "High"
    ? "text-ok"
    : value === "No" || value === "Low"
      ? "text-danger"
      : "text-warn";

const Stat = ({ label, value, tone }: { label: string; value?: string; tone?: string }) =>
  value ? (
    <div className="rounded-lg border border-border bg-bg/60 px-3 py-2.5">
      <dt className="eyebrow">{label}</dt>
      <dd className={`mt-1 text-sm font-semibold ${tone ?? "text-fg"}`}>{value}</dd>
    </div>
  ) : null;

const SectionBlock = ({ section, index }: { section: Section; index: number }) => (
  <section className="animate-rise" style={{ animationDelay: `${120 + index * 60}ms` }}>
    <h3 className="eyebrow">{section.title}</h3>
    {Array.isArray(section.content) ? (
      <ul className="mt-2 flex flex-wrap gap-2">
        {section.content.map((item) => (
          <li key={item} className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
            {item}
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-fg">{section.content}</p>
    )}
  </section>
);

export const ResultPanel = ({ result }: { result: AnalyzeResponse }) => {
  if (result.status === "blocked") {
    return (
      <div role="status" className="flex h-full animate-rise flex-col items-center justify-center gap-4 py-10 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-warn-soft">
          <ShieldAlert className="h-6 w-6 text-warn" />
        </span>
        <div>
          <h3 className="text-base font-semibold">Analysis withheld</h3>
          <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-subtle">{result.block?.message}</p>
        </div>
        <p className="max-w-sm text-xs text-subtle">
          Try rephrasing your reasoning, or run it again. The safety check would rather say nothing than give the answer away.
        </p>
      </div>
    );
  }

  const info = MODE_INFO[result.mode];
  return (
    <div className="space-y-6">
      <div className="animate-rise">
        <span className="eyebrow">Mistake type</span>
        <p className="mt-1.5 inline-block rounded-md bg-accent-soft px-3 py-1.5 font-mono text-sm font-medium text-accent">
          {result.mistake_type ?? "Unclassified"}
        </p>
      </div>

      <dl className="grid animate-rise grid-cols-1 gap-2 [animation-delay:60ms] sm:grid-cols-3">
        <Stat label="Pattern" value={result.reasoning_pattern} />
        <Stat label="Confidence" value={result.confidence} tone={toneFor(result.confidence)} />
        <Stat label={info.agreementLabel} value={result.agreement} tone={toneFor(result.agreement)} />
      </dl>

      <div className="space-y-5">
        {(result.sections ?? []).map((s, i) => (
          <SectionBlock key={s.key} section={s} index={i} />
        ))}
      </div>

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-4 text-xs text-subtle">
        <span className="inline-flex items-center gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5 text-ok" />
          {result.meta.judge_called ? "Passed safety check + judge" : "Passed safety check"}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          {(result.meta.latency_ms / 1000).toFixed(1)}s · {result.meta.model}
        </span>
      </footer>
    </div>
  );
};
