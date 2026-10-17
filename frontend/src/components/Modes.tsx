import { BookOpen, FlaskConical, Users } from "lucide-react";
import type { Mode } from "@/lib/api";
import { MODE_INFO } from "@/lib/examples";

const ICONS: Record<Mode, typeof BookOpen> = { education: BookOpen, interview: Users, research: FlaskConical };
const OUTPUTS: Record<Mode, string[]> = {
  education: ["What went wrong", "Why it happens", "How to rethink", "A reflection question"],
  interview: ["Interviewer assessment", "Risk signals", "Self-assessment check"],
  research: ["Cognitive pattern", "Why it occurs", "Broader implications", "Related biases"],
};

export const Modes = () => (
  <section id="modes" className="scroll-mt-14 border-b border-border">
    <div className="container-page py-20">
      <p className="eyebrow text-accent">Modes</p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight">One mistake, three lenses</h2>
      <p className="mt-2 max-w-2xl text-subtle">Each mode has its own persona and output structure.</p>

      <div className="mt-10 grid gap-5 md:grid-cols-3">
        {(Object.keys(MODE_INFO) as Mode[]).map((m) => {
          const Icon = ICONS[m];
          return (
            <article key={m} className="rounded-2xl border border-border bg-surface p-6 transition hover:-translate-y-0.5 hover:shadow-md">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-soft">
                <Icon className="h-5 w-5 text-accent" strokeWidth={1.75} />
              </span>
              <h3 className="mt-4 text-lg font-bold">{MODE_INFO[m].label}</h3>
              <p className="eyebrow mt-1">{MODE_INFO[m].focus}</p>
              <p className="mt-3 text-sm leading-relaxed text-subtle">{MODE_INFO[m].blurb}</p>
              <ul className="mt-4 space-y-1.5 border-t border-border pt-4 text-sm">
                {OUTPUTS[m].map((o) => (
                  <li key={o} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" /> {o}
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>
    </div>
  </section>
);
