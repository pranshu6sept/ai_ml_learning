import { describe, expect, it } from "vitest";
import { parseSource, splitCitations } from "./citations";

describe("splitCitations", () => {
  it("splits text and markers in order", () => {
    expect(splitCitations("A is true [1]. B follows [2][3].")).toEqual([
      { kind: "text", text: "A is true " },
      { kind: "cite", n: 1 },
      { kind: "text", text: ". B follows " },
      { kind: "cite", n: 2 },
      { kind: "cite", n: 3 },
      { kind: "text", text: "." },
    ]);
  });

  it("leaves text without markers as one piece", () => {
    expect(splitCitations("I don't know based on the provided documents.")).toEqual([
      { kind: "text", text: "I don't know based on the provided documents." },
    ]);
  });

  it("does not treat other bracketed text as a citation", () => {
    expect(splitCitations("see [note] and [1a] and [] and [1234]")).toEqual([
      { kind: "text", text: "see [note] and [1a] and [] and [1234]" },
    ]);
  });

  it("handles an empty answer", () => {
    expect(splitCitations("")).toEqual([]);
  });
});

describe("parseSource", () => {
  it("reads the document, section and link", () => {
    expect(parseSource("[1] iso20022_overview > ISO 20022 overview > Public summary (https://www.iso20022.org/)")).toEqual({
      n: 1,
      doc: "iso20022_overview",
      section: "ISO 20022 overview > Public summary",
      url: "https://www.iso20022.org/",
      note: "",
    });
  });

  it("shows a non-link location as a note, not a link", () => {
    const source = parseSource("[2] faqs > Payments FAQ starter set > FAQ 2 (internal_draft)");

    expect(source?.url).toBeNull();
    expect(source?.note).toBe("internal_draft");
  });

  it("never links anything but https", () => {
    for (const where of ["javascript:alert(1)", "http://example.org", "data:text/html,hi", "ftp://x"]) {
      expect(parseSource(`[1] doc > sec (${where})`)).toMatchObject({ url: null });
    }
  });

  it("keeps parentheses inside a URL or a section title", () => {
    const withUrl = parseSource("[1] doc > sec (https://en.wikipedia.org/wiki/ISO_20022_(standard))");
    const withTitle = parseSource("[2] faqs > FAQ 2 (what is it) > Details (https://x.org/a)");

    expect(withUrl?.url).toBe("https://en.wikipedia.org/wiki/ISO_20022_(standard)");
    expect(withTitle).toMatchObject({ doc: "faqs", section: "FAQ 2 (what is it) > Details", url: "https://x.org/a" });
  });

  it("shows a script address as plain text instead of dropping the source", () => {
    expect(parseSource("[1] doc > sec (javascript:alert(1))")).toMatchObject({ url: null, note: "javascript:alert(1)" });
  });

  it("returns null for a label it cannot read", () => {
    expect(parseSource("not a source label")).toBeNull();
    expect(parseSource("")).toBeNull();
  });
});
