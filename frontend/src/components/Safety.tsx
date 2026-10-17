import { Ban, Hash, Lock, Scale } from "lucide-react";

const layers = [
  {
    icon: Lock,
    title: "Instructed and fenced",
    body: "Every mode's prompt forbids solving, and your text is fenced off as data, so instructions hidden inside it are ignored.",
  },
  {
    icon: Ban,
    title: "Answer statements blocked",
    body: "Phrases that announce a result (\"the correct answer is…\", \"= 26\") are caught, while quoting your own answer is allowed.",
  },
  {
    icon: Hash,
    title: "New numbers get a second look",
    body: "If the analysis mentions a number that isn't in your problem or reasoning, in digits or in words, a judge model reviews it.",
  },
  {
    icon: Scale,
    title: "Fail-closed",
    body: "If the judge can't run, the analysis is withheld. A blocked response never carries the model's text.",
  },
];

export const Safety = () => (
  <section id="safety" className="scroll-mt-14 border-b border-border">
    <div className="container-page py-20">
      <p className="eyebrow text-accent">Safety</p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight">How it stays answer-free</h2>
      <p className="mt-2 max-w-2xl text-subtle">
        Several independent layers. None is perfect alone, so when in doubt the analysis is withheld.
      </p>
      <div className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2">
        {layers.map(({ icon: Icon, title, body }) => (
          <div key={title} className="flex gap-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
              <Icon className="h-4 w-4 text-accent" />
            </span>
            <div>
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-subtle">{body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
);
