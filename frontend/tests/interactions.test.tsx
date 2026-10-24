import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JobMatrix } from "../components/workbench";
import { IssuePanel } from "../components/issue-panel";
import { Courier } from "../components/courier";
import { SourceCard } from "../components/evidence";
import { actor, event, issue, job, order } from "./fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("workbench interactions", () => {
  it("selects a job and filters without changing the original denominator", async () => {
    const selected = vi.fn();
    render(
      <JobMatrix
        order={order({
          jobs: [
            job(),
            job({ id: "job-2", label: "Document 02", processing: "VALIDATED" }),
          ],
        })}
        onSelect={selected}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Document 01/ }));
    expect(selected).toHaveBeenCalledWith("job-1");
    await userEvent.click(screen.getByRole("button", { name: "Failed 1" }));
    expect(screen.queryByRole("button", { name: /Document 02/ })).toBeNull();
    expect(screen.getByText("1 shown / 100 original")).toBeTruthy();
  });
  it("keeps one issue conversation and submits the exact targeted question", async () => {
    const command = vi.fn().mockResolvedValue(true);
    const target = issue({
      messages: [
        ...issue().messages!,
        {
          id: "wrong",
          issue_id: "other-issue",
          author_id: "other",
          author_name: "Other",
          text: "DO NOT MIX THREADS",
          timestamp: "2026-10-23T10:00:00Z",
        },
      ],
    });
    render(
      <IssuePanel
        order={order()}
        issue={target}
        actor={actor}
        token="session"
        busy={false}
        command={command}
        mutate={vi.fn()}
      />,
    );
    expect(screen.queryByText("DO NOT MIX THREADS")).toBeNull();
    await userEvent.type(
      screen.getByLabelText("Answer this question"),
      "See the signed amendment.",
    );
    await userEvent.click(screen.getByRole("button", { name: /Send answer/ }));
    expect(command).toHaveBeenCalledWith(
      {
        verb: "answer",
        issue_id: "issue-1",
        question_id: "question-1",
        text: "See the signed amendment.",
      },
      "Targeted answer",
    );
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Answer this question") as HTMLTextAreaElement)
          .value,
      ).toBe(""),
    );
  });
  it("does not show answer authority to the wrong role", () => {
    render(
      <IssuePanel
        order={order()}
        issue={issue()}
        actor={{ id: "p", role: "provider", name: "Provider" }}
        token="session"
        busy={false}
        command={vi.fn()}
        mutate={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("Answer this question")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Investigate issue" }),
    ).toBeNull();
  });
  it("replay, history, animation end and return to live are read-only", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const view = render(
      <Courier
        events={[
          event(),
          event({ id: "event-2", sequence: 2, type: "check.passed" }),
        ]}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Replay events" }),
    );
    expect(screen.getByText("Read-only replay")).toBeTruthy();
    fireEvent.animationEnd(view.container.querySelector(".creature")!);
    await userEvent.click(
      screen.getByRole("button", { name: "Return to live" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "History" }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("blocks stale citation text/version/hash instead of inventing a source", () => {
    render(
      <SourceCard
        order={order({
          evidence: [
            {
              id: "s",
              version: 2,
              filename: "document.pdf",
              sha256: "a".repeat(64),
              media_type: "application/pdf",
              kind: "source",
              authority: "COMPANY_RECORD",
              text: "actual source",
              created_at: "2026-10-23",
              origin_actor_id: "provider",
            },
          ],
        })}
        sourceId="s"
        citation={{
          source_id: "s",
          version: 1,
          sha256: "b".repeat(64),
          quote: "invented",
          locator: "page 1",
        }}
        token="session"
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain("stale");
    expect(
      screen.queryByRole("button", { name: "Load verified artifact" }),
    ).toBeNull();
  });
});
