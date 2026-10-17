import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultPanel } from "@/components/ResultPanel";
import type { AnalyzeResponse } from "@/lib/api";

const meta = { model: "qwen2.5:3b", latency_ms: 4200, judge_called: false };

describe("ResultPanel", () => {
  it("renders summary, multi-line sections and list tags", () => {
    const result: AnalyzeResponse = {
      mode: "research",
      status: "ok",
      mistake_type: "Premature Closure",
      confidence: "High",
      agreement: "Partially",
      sections: [
        { key: "research_interpretation", title: "Research Interpretation", content: "Line one\nLine two" },
        { key: "related_cognitive_biases", title: "Related Cognitive Biases", content: ["Anchoring", "Framing"] },
      ],
      meta,
    };
    render(<ResultPanel result={result} />);
    expect(screen.getByText("Premature Closure")).toBeInTheDocument();
    expect(screen.getByText(/Line one/)).toHaveClass("whitespace-pre-line");
    expect(screen.getByText("Anchoring")).toBeInTheDocument();
    expect(screen.getByText("Agrees with your analysis")).toBeInTheDocument();
    expect(screen.getByText(/4\.2s/)).toBeInTheDocument();
  });

  it("shows only the block message when withheld", () => {
    const result: AnalyzeResponse = {
      mode: "education",
      status: "blocked",
      block: { reason: "explicit_answer", message: "The analysis started to state the answer." },
      meta,
    };
    render(<ResultPanel result={result} />);
    expect(screen.getByText("Analysis withheld")).toBeInTheDocument();
    expect(screen.getByText(/started to state the answer/)).toBeInTheDocument();
    expect(screen.queryByText("Mistake type")).not.toBeInTheDocument();
  });
});
