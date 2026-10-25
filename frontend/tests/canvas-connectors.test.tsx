import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

it("bounds repeated source-cell previews and keeps the evidence panel keyboard-accessible", async () => {
  const state = view({ produce: "done", review: "waiting", investigate: "running" });
  state.orb = {node:"investigate",mode:"inspect"};
  state.cards = Array.from({length:80}, (_,i)=>({id:`ref-${i}`,node:"investigate",text:i%2?"geography.csv":"coverage.csv",tone:"ev" as const}));
  const onNode=vi.fn();
  render(<Canvas nodes={nodes} view={state} focus={{kind:"overview"}} panelOpen={false} onNode={onNode}/>);
  expect(document.querySelectorAll(".ev")).toHaveLength(2);
  expect(screen.getAllByText("×40")).toHaveLength(2);
  expect(screen.getByText("Inspect all 80 references →")).toBeTruthy();
  fireEvent.click(screen.getByText("Inspect all 80 references →"));
  expect(onNode).toHaveBeenCalledWith("investigate");
  onNode.mockClear();
  screen.getByRole("button",{name:"investigate, running"}).focus();
  await userEvent.keyboard(" ");
  expect(onNode).toHaveBeenCalledWith("investigate");
  expect(state.cards).toHaveLength(80);
});

it("caps previews across distinct labels and preserves the full waiting reason in the chip title", () => {
  const state=view({investigate:"running",review:"waiting"});
  state.orb={node:"investigate",mode:"inspect"};
  state.chip.review="Waiting for an actual evidence answer; accepted scope and funding authority are unchanged.";
  state.cards=Array.from({length:40},(_,i)=>({id:`ref-${i}`,node:"investigate",text:`Source ${i} with a long label`,tone:"ev" as const}));
  draw(state);
  expect(document.querySelectorAll(".ev")).toHaveLength(2);
  expect(screen.getByTitle(state.chip.review!)).toBeTruthy();
  expect(screen.getByText("Inspect all 40 references →")).toBeTruthy();
});
