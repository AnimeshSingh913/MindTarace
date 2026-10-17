import { ArrowRight, EyeOff } from "lucide-react";

const steps = ["Problem", "Your reasoning", "Where it slipped", "How to rethink"];

export const Hero = () => (
  <section id="top" className="relative overflow-hidden border-b border-border">
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 opacity-60"
      style={{
        backgroundImage:
          "radial-gradient(ellipse 60% 50% at 50% 0%, hsl(var(--accent) / 0.14), transparent 70%)",
      }}
    />
    <div className="container-page relative py-20 text-center sm:py-28">
      <p className="mx-auto inline-flex animate-rise items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-subtle">
        <EyeOff className="h-3.5 w-3.5 text-accent" />
        Never shows the answer
      </p>
      <h1 className="mx-auto mt-6 max-w-3xl animate-rise text-4xl font-extrabold leading-[1.08] tracking-tight [animation-delay:60ms] sm:text-6xl">
        See where your reasoning
        <span className="text-accent"> went off track</span>
      </h1>
      <p className="mx-auto mt-5 max-w-xl animate-rise text-base leading-relaxed text-subtle [animation-delay:120ms] sm:text-lg">
        MindTrace analyses the thinking behind a wrong answer: the assumption, the misread, the shortcut.
        It explains the mistake and leaves the solving to you.
      </p>
      <div className="mt-9 flex animate-rise flex-wrap items-center justify-center gap-3 [animation-delay:180ms]">
        <a href="#analyze" className="btn-primary">
          Analyze reasoning <ArrowRight className="h-4 w-4" />
        </a>
        <a href="#modes" className="btn-ghost">Explore the modes</a>
      </div>

      <ol className="mx-auto mt-16 flex max-w-2xl animate-rise flex-wrap items-center justify-center gap-2 text-sm [animation-delay:260ms]">
        {steps.map((step, i) => (
          <li key={step} className="flex items-center gap-2">
            <span className="rounded-md border border-border bg-surface px-3 py-1.5 font-medium">
              <span className="mr-1.5 font-mono text-xs text-accent">{i + 1}</span>
              {step}
            </span>
            {i < steps.length - 1 && <span className="h-px w-4 bg-border" aria-hidden="true" />}
          </li>
        ))}
      </ol>
    </div>
  </section>
);
