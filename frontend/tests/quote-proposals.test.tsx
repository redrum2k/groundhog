import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChangeOrders } from "../components/change-orders";
import { actor, order } from "./fixtures";

afterEach(cleanup);

it("exposes the independent quote before a change order exists", () => {
  const command = vi.fn();
  const snapshot = order({
    change_orders: [],
    actions: [
      {
        id: "quote-1",
        kind: "QUOTE",
        issue_id: null,
        fields: ["purchase_order", "cost_center", "tax_id", "payment_terms"],
        job_ids: ["job-1"],
        amount_minor: 800,
        basis: "Declared field price schedule",
        revision: 1,
        agreement_version: 1,
        evidence_digest: "evidence",
        scope_digest: "scope",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
        owner: "controller",
        status: "PROPOSED",
      },
    ],
  });
  render(
    <ChangeOrders
      order={snapshot}
      actor={{ ...actor, id: "controller", role: "controller" }}
      token="local-test"
      busy={false}
      command={command}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Approve quote" }));
  expect(command).toHaveBeenCalledWith(
    { verb: "approve_action", action_id: "quote-1" },
    "Approve quote",
  );
});
