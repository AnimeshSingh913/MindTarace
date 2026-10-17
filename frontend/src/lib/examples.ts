import type { Mode } from "./api";

export interface Example {
  label: string;
  mode: Mode;
  problem: string;
  reasoning: string;
}

export const EXAMPLES: Example[] = [
  {
    label: "Percent speed-up",
    mode: "education",
    problem: "A train travels 120 km in 2 hours. If it speeds up by 50%, how long does the same journey take?",
    reasoning:
      "Original speed is 60 km/h. I first thought 50% faster meant multiplying, but then I decided it means adding 50 km/h, so the new speed is 110 km/h.",
  },
  {
    label: "Scaling WebSockets",
    mode: "interview",
    problem: "Design a system that handles 10,000 concurrent WebSocket connections with real-time updates.",
    reasoning:
      "I'd use a single Node.js server since it handles async well. Each connection keeps its state in memory. To scale, I'd add more RAM.",
  },
  {
    label: "AI tools study",
    mode: "research",
    problem: "A study reports: 'Students who use AI tools score 15% higher on exams.'",
    reasoning:
      "AI tools clearly improve learning. A 15% improvement is big, so schools should adopt AI tools immediately.",
  },
];

export const MODE_INFO: Record<Mode, { label: string; focus: string; blurb: string; agreementLabel: string }> = {
  education: {
    label: "Education",
    focus: "Learning & reflection",
    blurb: "A patient tutor that shows where thinking diverged and how to rethink it, without the solution.",
    agreementLabel: "Your explanation matches",
  },
  interview: {
    label: "Interview",
    focus: "Neutral evaluation",
    blurb: "An evaluator that surfaces reasoning risks and blind spots, with no coaching or hints.",
    agreementLabel: "Self-assessment matches",
  },
  research: {
    label: "Research",
    focus: "Cognitive patterns",
    blurb: "An analyst that abstracts the mistake into a general pattern and links related biases.",
    agreementLabel: "Agrees with your analysis",
  },
};
