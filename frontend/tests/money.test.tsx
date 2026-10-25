import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { formatMajor, formatMinor } from "../lib/money";
import LiveQuote from "../components/run/live-quote";
import type { Quote } from "../lib/runs.generated";

describe("exact minor-unit presentation", () => {
  it.each([[0,"0.00"],[1,"0.01"],[25,"0.25"],[50,"0.50"],[100,"1.00"],[101,"1.01"]])("formats %s cents", (minor, text) => {
    expect(formatMinor(minor as number)).toBe(text);
    expect(formatMajor((minor as number) / 100)).toBe(text);
  });
  it("does not round unsafe or fractional minor units into authorization", () => {
    expect(() => formatMinor(0.5)).toThrow();
    expect(() => formatMinor(Number.MAX_SAFE_INTEGER + 1)).toThrow();
  });
  it("shows a fractional quote and its exact atomic funding amount", () => {
    const quote = {amount:{amount_minor:25,decimals:2}, specification:{requirements:[],terms:{}}, payment_terms:{mode:"mock",amount_atomic:"250000",pricing_rule:"test",payment_info:{payer:"buyer",receiver:"provider",operator:"operator"}}} as unknown as Quote;
    render(<LiveQuote quote={quote} canAccept pay={()=>{}} />);
    expect(screen.getByRole("button", {name:"Accept & simulate $0.25"})).toBeTruthy();
    expect(screen.getByText(/Exact amount: 250000 atomic USDC/)).toBeTruthy();
  });
});
