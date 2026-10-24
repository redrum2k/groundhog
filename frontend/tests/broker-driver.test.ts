import { describe, expect, it } from "vitest";
import { parameters, sourceSnapshot } from "../lib/run/broker/driver";

describe("legacy broker demo source", () => {
  it("offers only released numeric rows with the same accepted coverage", () => {
    const source = sourceSnapshot("shared");
    const spec = parameters(new Date("2026-10-24T12:00:00Z"));
    expect(source.rows.length).toBeGreaterThan(0);
    expect(source.rows.every((row) => typeof row.value === "number" && row.value >= 50)).toBe(true);
    const keys = source.rows.map((row) => row.entity_id);
    expect(keys).toContain("94110");
    expect(keys).not.toContain("94129");
    expect(spec.region_ids).toEqual(keys);
    expect(spec.coverage_ids).toEqual(keys);
  });

  it("retains the grey case's missing observation date without inventing a count", () => {
    const row = sourceSnapshot("amber").rows.find((item) => item.entity_id === "94110");
    expect(row?.observed_at).toBeNull();
    expect(row?.value).toBeGreaterThanOrEqual(50);
  });
});
