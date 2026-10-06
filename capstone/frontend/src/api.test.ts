import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, ask, health, sendFeedback } from "./api";

const RESULT = {
  request_id: "abc123",
  question: "q",
  answer: "a [1]",
  sources: ["[1] d > s (https://x.org/)"],
  refused: false,
  reason: "ok",
  latency_ms: 1200,
};

function respond(body: unknown, status = 200, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status, headers }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("ask", () => {
  it("posts the question as JSON with the key in X-API-Key", async () => {
    const fetchMock = respond(RESULT);

    const result = await ask("What is ISO 20022?", "s3cret");

    expect(result.answer).toBe("a [1]");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/ask");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ question: "What is ISO 20022?" });
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("s3cret");
  });

  it("sends no key header when no key is set", async () => {
    const fetchMock = respond(RESULT);

    await ask("q", "");

    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).headers).not.toHaveProperty("X-API-Key");
  });

  it.each([
    [401, "auth"],
    [422, "validation"],
    [500, "server"],
    [502, "server"],
  ])("maps HTTP %i to the %s error", async (status, kind) => {
    respond({ detail: "x" }, status);

    await expect(ask("q", "k")).rejects.toMatchObject({ kind, status });
  });

  it("reads Retry-After on a 429", async () => {
    respond({ detail: "slow" }, 429, { "Retry-After": "12" });

    await expect(ask("q", "k")).rejects.toMatchObject({ kind: "rate_limit", retryAfter: 12 });
  });

  it("falls back to 30 seconds when Retry-After is missing or not a number", async () => {
    respond({ detail: "slow" }, 429, { "Retry-After": "soon" });

    await expect(ask("q", "k")).rejects.toMatchObject({ kind: "rate_limit", retryAfter: 30 });
  });

  it("turns a network failure into a friendly error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await ask("q", "k").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: "network", status: 0 });
  });

  it("does not hide a cancelled request as a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));

    await expect(ask("q", "k")).rejects.toMatchObject({ name: "AbortError" });
  });

  it("never puts server error text into the message", async () => {
    respond({ detail: "secret-endpoint.example.com refused" }, 502);

    const error = (await ask("q", "k").catch((e: unknown) => e)) as ApiError;

    expect(error.message).not.toContain("secret-endpoint");
  });
});

describe("sendFeedback and health", () => {
  it("posts the rating with the request id", async () => {
    const fetchMock = respond({ stored: true });

    await sendFeedback("abc123", "down", "k");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/feedback");
    expect(JSON.parse(init.body as string)).toEqual({ request_id: "abc123", rating: "down" });
  });

  it("reads the health endpoint without a key", async () => {
    const fetchMock = respond({ status: "ok", configured: true });

    await expect(health()).resolves.toEqual({ status: "ok", configured: true });
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("GET");
  });
});
