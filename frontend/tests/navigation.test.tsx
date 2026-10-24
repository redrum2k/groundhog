import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Workbench } from "../components/workbench";
import { useWorkbench } from "../lib/use-workbench";
import { actor, event, job, order } from "./fixtures";

vi.mock("../lib/use-workbench", () => ({ useWorkbench: vi.fn() }));
afterEach(() => cleanup());

function state(): ReturnType<typeof useWorkbench> {
  const current = order({
    jobs: [
      job({ dispute: "WAITING_CUSTOMER" }),
      job({ id: "job-2", label: "Document 02" }),
    ],
  });
  return {
    actors: [actor],
    session: { token: "session", actor },
    orders: [current],
    order: current,
    events: [event()],
    selectedId: current.id,
    error: undefined,
    notice: undefined,
    busy: false,
    loading: false,
    failed: undefined,
    refresh: vi.fn(),
    switchSession: vi.fn(),
    selectOrder: vi.fn(),
    mutate: vi.fn().mockResolvedValue(true),
    dismiss: vi.fn(),
  };
}
describe("focus, navigation and decision boundaries", () => {
  it("pauses opt-in auto-follow on manual focus and does not steal the selected job", async () => {
    const value = state();
    vi.mocked(useWorkbench).mockReturnValue(value);
    const view = render(<Workbench />);
    const follow = screen.getByRole("checkbox", {
      name: "Presentation auto-follow",
    });
    await userEvent.click(follow);
    expect((follow as HTMLInputElement).checked).toBe(true);
    const target = screen.getByRole("button", {
      name: /Document 01. Processing/,
    });
    fireEvent.focus(target);
    expect((follow as HTMLInputElement).checked).toBe(false);
    await userEvent.click(target);
    vi.mocked(useWorkbench).mockReturnValue({
      ...value,
      events: [
        ...value.events,
        event({ id: "event-2", sequence: 2, job_id: "job-2" }),
      ],
    });
    view.rerender(<Workbench />);
    expect(
      screen.getByRole("region", { name: "Job details: Document 01" }),
    ).toBeTruthy();
    expect(value.mutate).not.toHaveBeenCalled();
  });
  it("stops a bounded review pass instead of endlessly returning to waiting jobs", async () => {
    const value = state();
    vi.mocked(useWorkbench).mockReturnValue(value);
    render(<Workbench />);
    const next = screen.getByRole("button", { name: "Next unresolved →" });
    await userEvent.click(next);
    expect(screen.getByRole("status").textContent).toContain(
      "Waiting for a targeted response",
    );
    await userEvent.click(next);
    expect(
      screen.getByRole("region", { name: "Job details: Document 02" }),
    ).toBeTruthy();
    await userEvent.click(next);
    expect(screen.getByRole("status").textContent).toContain(
      "End of this review pass",
    );
    await userEvent.click(next);
    expect(screen.getByRole("status").textContent).toContain(
      "End of this review pass",
    );
    expect(value.mutate).not.toHaveBeenCalled();
  });
  it("keeps acceptance an explicit customer decision rather than a correction effect", async () => {
    const value = state();
    value.order = order({ jobs: [job({ processing: "VALIDATED" })] });
    value.orders = [value.order];
    vi.mocked(useWorkbench).mockReturnValue(value);
    render(<Workbench />);
    expect(value.mutate).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Accept 1 validated originals" }),
    );
    expect(value.mutate).toHaveBeenCalledTimes(1);
    const body = JSON.parse(vi.mocked(value.mutate).mock.calls[0][0].body);
    expect(body).toMatchObject({
      verb: "accept_delivery",
      job_ids: ["job-1"],
      expected_revision: 3,
    });
    expect(body).not.toHaveProperty("role");
  });
});
