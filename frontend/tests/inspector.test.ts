import { describe, expect, it } from "vitest";
import { lookFor } from "../components/run/inspector";
import type { ContractLine, Evidence, ZipCount } from "../lib/run/contract";

// Where the orb points after an objection, from the evidence alone: red only where the data fails a term.

const line = (id: string): ContractLine => ({ id, text: id, check: "code" });
const LIVE = ["freshness", "geography", "coverage"].map(line), RECORDED = ["city", "coverage"].map(line);
const quote = (id: string) => ({ id, kind: "interview_quote", label: id, note: "", quote: "", speaker: "Acme", source: { kind: "none", reason: "" } }) as Evidence;
const cell = (id: string, row = "") => ({ id, kind: "sheet_cell", label: id, note: "", file: "sheet.csv", row, column: "", value: null, source: { kind: "none", reason: "" } }) as Evidence;
const rows: ZipCount[] = [{ zip: "94102", area: "Tenderloin", count: 1820 }];

describe("lookFor", () => {
  it("points at the term a live citation names, in blue", () => {
    expect(lookFor([quote("cite-geography"), cell("cite-coverage")], LIVE, rows)).toEqual({ term: "geography", failed: false });
  });
  it("turns red on a term the backend's check failed", () => {
    expect(lookFor([quote("cite-geography"), cell("fail-2-freshness")], LIVE, rows)).toEqual({ term: "freshness", failed: true });
  });
  it("gives a recorded missing ZIP its own red row, then its term", () => {
    expect(lookFor([quote("e-line5"), cell("e-94110", "94110")], RECORDED, rows)).toEqual({ row: "94110", term: "coverage", failed: true });
  });
  it("points nowhere when no evidence names a term of this contract", () => {
    expect(lookFor([quote("e-wellness")], RECORDED, rows)).toBeNull();
    expect(lookFor([], LIVE, rows)).toBeNull();
  });
});
