// A small client for the payments assistant API. Same origin by default (the API serves this page, and the
// Vite dev server proxies to it), so no CORS. `VITE_API_BASE` points it somewhere else if ever needed.

const BASE: string = import.meta.env.VITE_API_BASE ?? "";

export const MAX_QUESTION_CHARS = 1000;

export interface AskResult {
  request_id: string;
  question: string;
  answer: string;
  sources: string[];
  refused: boolean;
  reason: string;
  latency_ms: number;
}

export interface Health {
  status: string;
  configured: boolean;
}

export type ErrorKind = "auth" | "validation" | "rate_limit" | "server" | "network";

export class ApiError extends Error {
  readonly kind: ErrorKind;
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(kind: ErrorKind, status: number, message: string, retryAfter: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

function headers(apiKey: string): Record<string, string> {
  const out: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) out["X-API-Key"] = apiKey;
  return out;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("network", 0, "Could not reach the API. Check your connection and try again.");
  }
  if (response.ok) return (await response.json()) as T;

  if (response.status === 401) {
    throw new ApiError("auth", 401, "The API key is missing or wrong.");
  }
  if (response.status === 422) {
    throw new ApiError("validation", 422, `The question was not accepted (1 to ${MAX_QUESTION_CHARS} characters).`);
  }
  if (response.status === 429) {
    const seconds = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
    const retryAfter = Number.isFinite(seconds) && seconds > 0 ? seconds : 30;
    throw new ApiError("rate_limit", 429, `Too many requests. Try again in ${retryAfter} s.`, retryAfter);
  }
  throw new ApiError("server", response.status, "The assistant could not answer right now. Try again.");
}

export function ask(question: string, apiKey: string, signal?: AbortSignal): Promise<AskResult> {
  return request<AskResult>("/ask", {
    method: "POST",
    headers: headers(apiKey),
    body: JSON.stringify({ question }),
    signal,
  });
}

export function sendFeedback(
  requestId: string,
  rating: "up" | "down",
  apiKey: string,
): Promise<{ stored: boolean }> {
  return request<{ stored: boolean }>("/feedback", {
    method: "POST",
    headers: headers(apiKey),
    body: JSON.stringify({ request_id: requestId, rating }),
  });
}

export function health(signal?: AbortSignal): Promise<Health> {
  return request<Health>("/health", { method: "GET", signal });
}
