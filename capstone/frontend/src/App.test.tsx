import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

type Reply = { status?: number; body: unknown; headers?: Record<string, string> };

const ANSWER = {
  request_id: "req00001abcdef",
  question: "What is ISO 20022?",
  answer: "ISO 20022 is a global standard [1]. It is adopted widely [2].",
  sources: [
    "[1] iso20022_overview > ISO 20022 overview > Public summary (https://www.iso20022.org/)",
    "[2] faqs > Payments FAQ > FAQ 2 (internal_draft)",
  ],
  refused: false,
  reason: "passages judged to answer the question",
  latency_ms: 2300,
};

const REFUSAL = {
  request_id: "req00002abcdef",
  question: "Who won?",
  answer: "I don't know based on the provided documents.",
  sources: [],
  refused: true,
  reason: "the passages were judged 'none'",
  latency_ms: 900,
};

let calls: { path: string; body: Record<string, unknown> | null; key: string | null }[];

function serve(routes: Record<string, Reply | (() => Reply)>) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const headers = (init?.headers ?? {}) as Record<string, string>;
      calls.push({
        path: url,
        body: init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : null,
        key: headers["X-API-Key"] ?? null,
      });
      const route = routes[url];
      if (!route) throw new TypeError("no route");
      const reply = typeof route === "function" ? route() : route;
      return new Response(JSON.stringify(reply.body), { status: reply.status ?? 200, headers: reply.headers });
    }),
  );
}

const HEALTH = { body: { status: "ok", configured: true } };

beforeEach(() => serve({ "/health": HEALTH, "/ask": { body: ANSWER }, "/feedback": { body: { stored: true } } }));
afterEach(() => vi.unstubAllGlobals());

async function ask(user: ReturnType<typeof userEvent.setup>, text = "What is ISO 20022?") {
  await user.type(screen.getByLabelText("Your question"), text);
  await user.click(screen.getByRole("button", { name: "Ask" }));
}

describe("the page", () => {
  it("shows whether the service is online", async () => {
    render(<App />);

    expect(await screen.findByText("Service online")).toBeInTheDocument();
  });

  it("says when the service is unreachable", async () => {
    serve({});
    render(<App />);

    expect(await screen.findByText("Service unreachable")).toBeInTheDocument();
  });

  it("warns when the service is up but Azure is not configured", async () => {
    serve({ "/health": { body: { status: "ok", configured: false } } });
    render(<App />);

    expect(await screen.findByText(/Azure is not configured/)).toBeInTheDocument();
  });

  it("sends the question with the key and shows a cited answer with its sources", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("API key"), "s3cret");

    await ask(user);

    const card = await screen.findByRole("article");
    expect(within(card).getByText(/ISO 20022 is a global standard/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Source 1" })).toHaveAttribute("href", expect.stringMatching(/^#src-\d+-1$/));
    expect(within(card).getByRole("link", { name: "open source" })).toHaveAttribute("href", "https://www.iso20022.org/");
    expect(within(card).getByText("(internal_draft)")).toBeInTheDocument(); // not a link
    const asked = calls.find((c) => c.path === "/ask");
    expect(asked?.body).toEqual({ question: "What is ISO 20022?" });
    expect(asked?.key).toBe("s3cret");
    expect(screen.getByLabelText("Your question")).toHaveValue(""); // cleared after a good answer
  });

  it("opens source links safely", async () => {
    const user = userEvent.setup();
    render(<App />);

    await ask(user);

    const link = await screen.findByRole("link", { name: "open source" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows a refusal as a refusal, with the reason", async () => {
    serve({ "/health": HEALTH, "/ask": { body: REFUSAL } });
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "Who won?");

    expect(await screen.findByText("No answer from the documents")).toBeInTheDocument();
    expect(screen.getByText(/Why: the passages were judged 'none'/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sources" })).not.toBeInTheDocument();
  });

  it("renders a hostile answer as plain text, never as markup", async () => {
    const hostile = { ...ANSWER, answer: '<img src=x onerror="alert(1)"> <b>bold</b> [1]', sources: ANSWER.sources.slice(0, 1) };
    serve({ "/health": HEALTH, "/ask": { body: hostile } });
    const user = userEvent.setup();
    render(<App />);

    await ask(user);

    const card = await screen.findByRole("article");
    expect(card.querySelector("img")).toBeNull();
    expect(card.querySelector("b")).toBeNull();
    expect(within(card).getByText(/<img src=x/)).toBeInTheDocument();
  });

  it("marks a citation number the API did not return as unavailable instead of linking it", async () => {
    const odd = { ...ANSWER, answer: "Claim [7].", sources: ANSWER.sources.slice(0, 1) };
    serve({ "/health": HEALTH, "/ask": { body: odd } });
    const user = userEvent.setup();
    render(<App />);

    await ask(user);

    const card = await screen.findByRole("article");
    expect(within(card).queryByRole("link", { name: "Source 7" })).not.toBeInTheDocument();
    expect(within(card).getByTitle("This source number was not returned")).toHaveTextContent("7");
  });

  it("submits on Enter but not on Shift+Enter", async () => {
    const user = userEvent.setup();
    render(<App />);
    const box = screen.getByLabelText("Your question");

    await user.type(box, "first line{Shift>}{Enter}{/Shift}second");
    expect(calls.some((c) => c.path === "/ask")).toBe(false);
    expect(box).toHaveValue("first line\nsecond");

    await user.type(box, "{Enter}");
    await waitFor(() => expect(calls.some((c) => c.path === "/ask")).toBe(true));
  });

  it("asks an example question with one click", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "What is UPI?" }));

    await waitFor(() => expect(calls.find((c) => c.path === "/ask")?.body).toEqual({ question: "What is UPI?" }));
  });

  it("does not send an empty question, and blocks one over the limit", async () => {
    const user = userEvent.setup();
    render(<App />);
    const button = screen.getByRole("button", { name: "Ask" });
    expect(button).toBeDisabled();

    await user.click(screen.getByLabelText("Your question"));
    await user.paste("x".repeat(1001));

    expect(button).toBeDisabled();
    expect(screen.getByText("1001 / 1000")).toHaveClass("over");
    expect(calls.some((c) => c.path === "/ask")).toBe(false);
  });
});

describe("errors", () => {
  it("tells the user to paste the key after a 401", async () => {
    serve({ "/health": HEALTH, "/ask": { status: 401, body: { detail: "x" } } });
    const user = userEvent.setup();
    render(<App />);

    await ask(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(/API key is missing or wrong.*Paste the key/);
    expect(screen.getByLabelText("Your question")).toHaveValue("What is ISO 20022?"); // the question is kept
  });

  it("counts down after a 429 and disables asking meanwhile", async () => {
    serve({ "/health": HEALTH, "/ask": { status: 429, body: { detail: "slow" }, headers: { "Retry-After": "7" } } });
    const user = userEvent.setup();
    render(<App />);

    await ask(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 7 s");
    expect(screen.getByRole("button", { name: "Wait 7 s" })).toBeDisabled();
  });

  it("shows a friendly message for a server error without leaking details", async () => {
    serve({ "/health": HEALTH, "/ask": { status: 502, body: { detail: "internal-host refused" } } });
    const user = userEvent.setup();
    render(<App />);

    await ask(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("could not answer right now");
    expect(alert).not.toHaveTextContent("internal-host");
  });
});

describe("the API key", () => {
  it("is kept in session storage only, and restored on reload", async () => {
    const user = userEvent.setup();
    const first = render(<App />);

    await user.type(screen.getByLabelText("API key"), "abc");

    expect(window.sessionStorage.getItem("payrag_api_key")).toBe("abc");
    expect(window.localStorage.getItem("payrag_api_key")).toBeNull();
    first.unmount();
    render(<App />);
    expect(screen.getByLabelText("API key")).toHaveValue("abc");
  });

  it("is a password field with autocomplete off", () => {
    render(<App />);

    const field = screen.getByLabelText("API key");
    expect(field).toHaveAttribute("type", "password");
    expect(field).toHaveAttribute("autocomplete", "off");
  });

  it("is forgotten when the field is cleared", async () => {
    const user = userEvent.setup();
    render(<App />);
    const field = screen.getByLabelText("API key");

    await user.type(field, "abc");
    await user.clear(field);

    expect(window.sessionStorage.getItem("payrag_api_key")).toBeNull();
  });
});

describe("feedback", () => {
  it("posts the rating with the request id and thanks the user", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("API key"), "k");
    await ask(user);

    await user.click(await screen.findByRole("button", { name: "This answer was helpful" }));

    expect(await screen.findByText("Thanks for the feedback.")).toBeInTheDocument();
    const sent = calls.find((c) => c.path === "/feedback");
    expect(sent?.body).toEqual({ request_id: "req00001abcdef", rating: "up" });
    expect(sent?.key).toBe("k");
  });

  it("says so when feedback could not be sent, and lets the user retry", async () => {
    serve({ "/health": HEALTH, "/ask": { body: ANSWER }, "/feedback": { status: 500, body: {} } });
    const user = userEvent.setup();
    render(<App />);
    await ask(user);

    await user.click(await screen.findByRole("button", { name: "This answer was not helpful" }));

    expect(await screen.findByText(/Could not send feedback/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "This answer was not helpful" })).toBeEnabled();
  });
});

describe("history", () => {
  it("keeps earlier answers below the newest one", async () => {
    let n = 0;
    serve({
      "/health": HEALTH,
      "/ask": () => ({ body: { ...ANSWER, request_id: `req${++n}`, question: `Question ${n}`, answer: `Answer ${n} [1].` } }),
    });
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "one");
    await screen.findByText(/Answer 1/);
    await ask(user, "two");

    const headings = await screen.findAllByRole("heading", { level: 2 });
    expect(headings.map((h) => h.textContent)).toEqual(["Question 2", "Question 1"]);
  });
});
