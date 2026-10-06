import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, MAX_QUESTION_CHARS, ask, health } from "./api";
import type { Health } from "./api";
import { AnswerCard } from "./components/AnswerCard";
import type { Entry } from "./components/AnswerCard";

const KEY_STORAGE = "payrag_api_key";
const MAX_HISTORY = 20;
const EXAMPLES = [
  "What is ISO 20022?",
  "What is remittance information?",
  "Who does PCI DSS apply to?",
  "What is UPI?",
  "Who won the cricket world cup in 2011?",
];

// The key lives in this tab only (sessionStorage), never in the build, and is cleared when the tab closes.
function loadKey(): string {
  try {
    return window.sessionStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

function saveKey(value: string): void {
  try {
    if (value) window.sessionStorage.setItem(KEY_STORAGE, value);
    else window.sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage can be blocked (private mode); the key then lasts until the page is closed */
  }
}

type Status = { state: "checking" } | { state: "up"; configured: boolean } | { state: "down" };

export default function App() {
  const [apiKey, setApiKey] = useState(loadKey);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [status, setStatus] = useState<Status>({ state: "checking" });
  const [wait, setWait] = useState(0);
  const nextId = useRef(1);

  useEffect(() => {
    const controller = new AbortController();
    health(controller.signal)
      .then((h: Health) => setStatus({ state: "up", configured: h.configured }))
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setStatus({ state: "down" });
      });
    return () => controller.abort();
  }, []);

  // Count down after a rate-limit response, so the button comes back by itself.
  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait((w) => w - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  function updateKey(value: string) {
    setApiKey(value);
    saveKey(value);
  }

  async function submit(event?: FormEvent, text: string = question) {
    event?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || loading || wait > 0) return;
    setLoading(true);
    setError(null);
    try {
      const result = await ask(trimmed, apiKey);
      const entry: Entry = { id: nextId.current++, result };
      setEntries((previous) => [entry, ...previous].slice(0, MAX_HISTORY));
      setQuestion("");
    } catch (e) {
      const apiError = e instanceof ApiError ? e : new ApiError("server", 0, "Something went wrong. Try again.");
      setError(apiError);
      if (apiError.kind === "rate_limit" && apiError.retryAfter) setWait(apiError.retryAfter);
    } finally {
      setLoading(false);
    }
  }

  const tooLong = question.length > MAX_QUESTION_CHARS;
  const blocked = loading || wait > 0 || !question.trim() || tooLong;

  return (
    <main>
      <header className="top">
        <h1>Payments Assistant</h1>
        <p className="tagline">Answers about payments and banking rules, from a small set of public documents. It cites its sources, or says it does not know.</p>
        <p className={`status ${status.state}`} role="status">
          {status.state === "checking" && "Checking the service..."}
          {status.state === "up" && (status.configured ? "Service online" : "Service online, but Azure is not configured")}
          {status.state === "down" && "Service unreachable"}
        </p>
      </header>

      <form onSubmit={submit} className="ask" aria-label="Ask a question">
        <label htmlFor="apikey">API key</label>
        <input
          id="apikey"
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(e) => updateKey(e.target.value)}
          placeholder="Paste the key (kept in this tab only)"
        />

        <label htmlFor="question">Your question</label>
        <textarea
          id="question"
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          aria-describedby="count"
          placeholder="For example: What is ISO 20022?"
        />
        <div className="row">
          <span id="count" className={tooLong ? "over" : ""}>
            {question.length} / {MAX_QUESTION_CHARS}
          </span>
          <button type="submit" disabled={blocked}>
            {loading ? "Thinking..." : wait > 0 ? `Wait ${wait} s` : "Ask"}
          </button>
        </div>

        <div className="examples" aria-label="Example questions">
          {EXAMPLES.map((example) => (
            <button key={example} type="button" className="chip" disabled={loading || wait > 0} onClick={() => { setQuestion(example); void submit(undefined, example); }}>
              {example}
            </button>
          ))}
        </div>
      </form>

      <div aria-live="polite">
        {error && (
          <p className="error" role="alert">
            {error.message}
            {error.kind === "auth" && " Paste the key in the field above."}
          </p>
        )}
        {loading && <p className="loading">Searching the documents...</p>}
      </div>

      <section aria-label="Answers">
        {entries.map((entry) => (
          <AnswerCard key={entry.id} entry={entry} apiKey={apiKey} />
        ))}
      </section>
    </main>
  );
}
