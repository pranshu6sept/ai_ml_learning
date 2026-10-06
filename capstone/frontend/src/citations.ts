// Turning the model's cited answer into pieces the page can render safely. Nothing here produces HTML:
// the page renders text nodes and React elements only, so a hostile answer cannot inject markup.

export type Piece = { kind: "text"; text: string } | { kind: "cite"; n: number };

/** Split "X is true [1]. Y follows [2][3]." into text and citation pieces, in order. */
export function splitCitations(answer: string): Piece[] {
  const pieces: Piece[] = [];
  const marker = /\[(\d{1,3})\]/g;
  let last = 0;
  for (const match of answer.matchAll(marker)) {
    const start = match.index ?? 0;
    if (start > last) pieces.push({ kind: "text", text: answer.slice(last, start) });
    pieces.push({ kind: "cite", n: Number.parseInt(match[1] ?? "0", 10) });
    last = start + match[0].length;
  }
  if (last < answer.length) pieces.push({ kind: "text", text: answer.slice(last) });
  return pieces;
}

export interface Source {
  n: number;
  doc: string;
  section: string;
  /** Only an https address is ever linked; anything else (for example "internal_draft") is shown as text. */
  url: string | null;
  note: string;
}

/** Parse "[1] iso20022_overview > ISO 20022 overview > Public summary (https://www.iso20022.org/)". */
export function parseSource(label: string): Source | null {
  // Split at the LAST " (": a section title may contain parentheses, and so may a URL ("..._(Y)").
  const match = /^\[(\d{1,3})\]\s+(.*)\s+\((.*)\)\s*$/.exec(label);
  if (!match) return null;
  const n = Number.parseInt(match[1] ?? "0", 10);
  const path = (match[2] ?? "").split(">").map((part) => part.trim());
  const where = (match[3] ?? "").trim();
  const isLink = /^https:\/\/[^\s]+$/i.test(where);
  return {
    n,
    doc: path[0] ?? "",
    section: path.slice(1).join(" > "),
    url: isLink ? where : null,
    note: isLink ? "" : where,
  };
}
