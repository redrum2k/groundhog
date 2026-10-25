import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Canvas, { type CNode, type CanvasView } from "../components/run/canvas";

class ResizeObserverStub { observe() {} disconnect() {} }
beforeEach(() => vi.stubGlobal("ResizeObserver", ResizeObserverStub));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const nodes: CNode[] = [
  ...["clarify", "paid", "produce", "review", "captured"].map((id, col) => ({ id, row: 0, col, title: id, desc: "" })),
  ...["investigate", "verdict", "decide"].map((id, col) => ({ id, row: 1, col, title: id, desc: "" })),
];
const view = (status: CanvasView["status"], loops: string[] = []): CanvasView => ({
  status, chip: {}, orb: null, coin: null, loops, cards: [],
});
const draw = (state: CanvasView, steps = nodes) => render(
  <Canvas nodes={steps} view={state} focus={{ kind: "overview" }} panelOpen={false} onNode={() => {}} />,
);
const detours = () => document.querySelectorAll('.edges path[d*=" V"]');

it("does not draw a branch from hidden customer review when funding needs human review", () => {
  draw(view({ clarify: "done", paid: "waiting", decide: "waiting" }));
  expect(screen.queryByRole("button", { name: "review, idle" })).toBeNull();
  expect(screen.getByRole("button", { name: "decide, waiting" })).toBeTruthy();
  expect(detours()).toHaveLength(0);
  expect(screen.queryByText("back to Produce")).toBeNull();
});

it("does not draw a detour before review starts, even when its card is ghosted", () => {
  draw(view({ clarify: "done", paid: "done", produce: "running" }));
  expect(screen.getByRole("button", { name: "review, idle" })).toBeTruthy();
  expect(detours()).toHaveLength(0);
});

it("connects review to investigation without returning from a hidden human-review card", () => {
  draw(view({ produce: "done", review: "waiting", investigate: "running" }));
  expect(detours()).toHaveLength(2); // dashed branch and its progress overlay
  expect(screen.queryByText("back to Produce")).toBeNull();
});

it("keeps the connected return path once the final detour step is visible", () => {
  const state = view({ produce: "done", review: "waiting", decide: "waiting" });
  const { rerender } = draw(state);
  expect(screen.getByText("back to Produce")).toBeTruthy();
  expect(detours()).toHaveLength(3);
  rerender(<Canvas nodes={nodes} view={{ ...state, loops: ["decide"] }} focus={{ kind: "overview" }} panelOpen={false} onNode={() => {}} />);
  expect(document.querySelector(".loop")).not.toBeNull();
  expect(screen.queryByText("back to Produce")).toBeNull();
});

it("does not invent connectors when a partial plan has no review or production step", () => {
  draw(view({ clarify: "waiting", decide: "waiting" }), nodes.filter(n => ["clarify", "decide"].includes(n.id)));
  expect(detours()).toHaveLength(0);
  expect(screen.queryByText("back to Produce")).toBeNull();
});
