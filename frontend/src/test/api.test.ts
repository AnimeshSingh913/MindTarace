import { afterEach, describe, expect, it, vi } from "vitest";
import { analyze, ApiError } from "@/lib/api";

const body = { problem: "p", reasoning: "r", mode: "education" as const };

function mockFetch(impl: (...args: unknown[]) => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => vi.unstubAllGlobals());

describe("analyze()", () => {
  it("returns the parsed body on success", async () => {
    mockFetch(async () => new Response(JSON.stringify({ status: "ok", mode: "education" }), { status: 200 }));
    await expect(analyze(body)).resolves.toMatchObject({ status: "ok" });
  });

  it.each([
    [503, "unavailable"],
    [502, "model"],
    [422, "validation"],
    [500, "server"],
  ])("maps HTTP %i to %s", async (status, kind) => {
    mockFetch(async () => new Response(JSON.stringify({ detail: "boom" }), { status }));
    const err = await analyze(body).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.kind).toBe(kind);
  });

  it("adds a wait hint from Retry-After on 429", async () => {
    mockFetch(
      async () =>
        new Response(JSON.stringify({ detail: "Too many analyses." }), { status: 429, headers: { "Retry-After": "42" } }),
    );
    const err = await analyze(body).catch((e) => e);
    expect(err.kind).toBe("rate_limited");
    expect(err.message).toBe("Too many analyses. You can try again in about 42 seconds.");
  });

  it("formats pydantic validation details", async () => {
    const detail = [{ loc: ["body", "problem"], msg: "Value error, must not be empty" }];
    mockFetch(async () => new Response(JSON.stringify({ detail }), { status: 422 }));
    const err = await analyze(body).catch((e) => e);
    expect(err.message).toBe("problem: must not be empty");
  });

  it("reports network failures clearly", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const err = await analyze(body).catch((e) => e);
    expect(err.kind).toBe("network");
  });
});
