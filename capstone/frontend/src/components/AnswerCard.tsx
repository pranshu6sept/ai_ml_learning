import { useState } from "react";
import type { AskResult } from "../api";
import { sendFeedback } from "../api";
import { parseSource, splitCitations } from "../citations";

export interface Entry {
  id: number;
  result: AskResult;
}

interface Props {
  entry: Entry;
  apiKey: string;
}

type FeedbackState = "none" | "sending" | "up" | "down" | "failed";

export function AnswerCard({ entry, apiKey }: Props) {
  const { result } = entry;
  const [feedback, setFeedback] = useState<FeedbackState>("none");
  const sources = result.sources.map(parseSource).filter((s) => s !== null);
  const known = new Set(sources.map((s) => s.n));

  async function rate(rating: "up" | "down") {
    setFeedback("sending");
    try {
      await sendFeedback(result.request_id, rating, apiKey);
      setFeedback(rating);
    } catch {
      setFeedback("failed");
    }
  }

  return (
    <article className={`card${result.refused ? " refused" : ""}`} aria-label={`Answer to: ${result.question}`}>
      <h2 className="question">{result.question}</h2>

      {result.refused && (
        <p className="badge" role="note">
          No answer from the documents
        </p>
      )}

      <p className="answer">
        {splitCitations(result.answer).map((piece, index) =>
          piece.kind === "text" ? (
            <span key={index}>{piece.text}</span>
          ) : known.has(piece.n) ? (
            <a key={index} className="cite" href={`#src-${entry.id}-${piece.n}`} aria-label={`Source ${piece.n}`}>
              {piece.n}
            </a>
          ) : (
            <sup key={index} className="cite missing" title="This source number was not returned">
              {piece.n}
            </sup>
          ),
        )}
      </p>

      {result.refused && result.reason && <p className="reason">Why: {result.reason}.</p>}

      {sources.length > 0 && (
        <section aria-label="Sources">
          <h3>Sources</h3>
          <ol className="sources">
            {sources.map((source) => (
              <li key={source.n} id={`src-${entry.id}-${source.n}`} value={source.n}>
                <span className="doc">{source.doc}</span>
                {source.section && <span className="section"> &rsaquo; {source.section}</span>}{" "}
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noopener noreferrer">
                    open source
                  </a>
                ) : (
                  source.note && <span className="note">({source.note})</span>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer className="meta">
        <span>{(result.latency_ms / 1000).toFixed(1)} s</span>
        <span className="rid" title={result.request_id}>
          id {result.request_id.slice(0, 8)}
        </span>
        <span className="feedback">
          {feedback === "up" || feedback === "down" ? (
            <span role="status">Thanks for the feedback.</span>
          ) : (
            <>
              <button type="button" onClick={() => rate("up")} disabled={feedback === "sending"} aria-label="This answer was helpful">
                &#128077;
              </button>
              <button type="button" onClick={() => rate("down")} disabled={feedback === "sending"} aria-label="This answer was not helpful">
                &#128078;
              </button>
              {feedback === "failed" && <span role="alert"> Could not send feedback.</span>}
            </>
          )}
        </span>
      </footer>
    </article>
  );
}
