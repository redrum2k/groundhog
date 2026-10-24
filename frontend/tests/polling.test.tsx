import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWorkbench } from "../lib/use-workbench";
import { prepareMutation } from "../lib/api";
import { actor, event, order, provider } from "./fixtures";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
beforeEach(() => sessionStorage.clear());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function router(
  override?: (
    path: string,
    init?: RequestInit,
  ) => Promise<Response> | undefined,
) {
  return vi.fn((path: string, init?: RequestInit) => {
    const custom = override?.(path, init);
    if (custom) return custom;
    if (path.endsWith("/actors"))
      return Promise.resolve(json([actor, provider]));
    if (path.endsWith("/sessions")) {
      const chosen =
        JSON.parse(String(init?.body)).actor_id === provider.id
          ? provider
          : actor;
      return Promise.resolve(
        json({ token: `token-${chosen.id}`, actor: chosen }),
      );
    }
    if (path.endsWith("/orders"))
      return Promise.resolve(
        json([order(), order({ id: "order-2", title: "Second batch" })]),
      );
    if (path.includes("/events?"))
      return Promise.resolve(
        json([
          event({ order_id: path.includes("order-2") ? "order-2" : "order-1" }),
        ]),
      );
    if (path.endsWith("/orders/order-2"))
      return Promise.resolve(
        json(order({ id: "order-2", title: "Second batch" })),
      );
    return Promise.resolve(json(order()));
  });
}
async function signedIn(override?: Parameters<typeof router>[0]) {
  const fetcher = router(override);
  vi.stubGlobal("fetch", fetcher);
  const hook = renderHook(() => useWorkbench());
  await waitFor(() => expect(hook.result.current.actors.length).toBe(2));
  await act(() => hook.result.current.switchSession(actor.id));
  await waitFor(() => expect(hook.result.current.order?.id).toBe("order-1"));
  return { ...hook, fetcher };
}

describe("polling and mutation lifecycle", () => {
  it("keeps the selected order live when its sidebar entry is clicked again", async () => {
    const { result } = await signedIn();
    act(() => result.current.selectOrder("order-1"));
    expect(result.current.order?.id).toBe("order-1");
    expect(result.current.events).toHaveLength(1);
  });
  it("does not mutate during render, polling or refresh", async () => {
    const { result, fetcher } = await signedIn();
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const posts = fetcher.mock.calls.filter(
      ([, init]) => init?.method === "POST",
    );
    expect(posts).toHaveLength(1);
    expect(posts[0][0]).toBe("/api/jobflow/sessions");
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
      actor_id: actor.id,
    });
  });
  it("shows 409, refreshes, and never resubmits the stale command", async () => {
    const { result, fetcher } = await signedIn((path) =>
      path.endsWith("/commands")
        ? Promise.resolve(json({ detail: "stale revision" }, 409))
        : undefined,
    );
    const command = prepareMutation(
      "/orders/order-1/commands",
      { verb: "accept_delivery", job_ids: ["job-1"] },
      "Accept",
      3,
    );
    await act(() => result.current.mutate(command));
    expect(result.current.error).toContain("409");
    expect(result.current.failed).toBeUndefined();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(
      fetcher.mock.calls.filter(([path]) => path.endsWith("/commands")),
    ).toHaveLength(1);
  });
  it("blocks a fresh mutation after response loss and retries the exact original", async () => {
    let calls = 0;
    const { result, fetcher } = await signedIn((path) =>
      path.endsWith("/commands")
        ? ++calls === 1
          ? Promise.reject(new Error("connection lost"))
          : Promise.resolve(json(order({ revision: 4 })))
        : undefined,
    );
    const command = prepareMutation(
      "/orders/order-1/commands",
      { verb: "accept_delivery", job_ids: ["job-1"] },
      "Accept",
      3,
    );
    await act(() => result.current.mutate(command));
    expect(result.current.failed).toBe(command);
    await act(() =>
      result.current.mutate(
        prepareMutation(
          "/orders/order-1/commands",
          { verb: "accept_delivery" },
          "New decision",
          3,
        ),
      ),
    );
    expect(calls).toBe(1);
    await act(() => result.current.mutate(command));
    expect(calls).toBe(2);
    const posts = fetcher.mock.calls.filter(([path]) =>
      path.endsWith("/commands"),
    );
    expect(posts[0][1]?.body).toBe(posts[1][1]?.body);
    expect(result.current.failed).toBeUndefined();
    expect(result.current.order?.revision).toBe(4);
  });
  it("ignores late order responses after switching orders", async () => {
    let resolveLate!: (value: Response) => void;
    let delay = false;
    const { result } = await signedIn((path) =>
      delay && path.endsWith("/orders/order-1")
        ? new Promise<Response>((resolve) => {
            resolveLate = resolve;
          })
        : undefined,
    );
    delay = true;
    act(() => result.current.refresh());
    await waitFor(() => expect(resolveLate).toBeTypeOf("function"));
    act(() => result.current.selectOrder("order-2"));
    await waitFor(() => expect(result.current.order?.id).toBe("order-2"));
    await act(async () => {
      resolveLate(json(order({ revision: 999 })));
      await Promise.resolve();
    });
    expect(result.current.order?.id).toBe("order-2");
    expect(result.current.events.every((e) => e.order_id === "order-2")).toBe(
      true,
    );
  });
  it("stores identity only in session storage and resets state on session change", async () => {
    const { result, fetcher } = await signedIn();
    await act(() => result.current.switchSession(provider.id));
    await waitFor(() => expect(result.current.order).toBeDefined());
    expect(result.current.session?.actor.id).toBe(provider.id);
    expect(localStorage.getItem("jobflow.session")).toBeNull();
    expect(
      JSON.parse(sessionStorage.getItem("jobflow.session")!).actor.id,
    ).toBe(provider.id);
    const lastRead = fetcher.mock.calls
      .filter(([path]) => path.endsWith("/orders/order-1"))
      .at(-1)!;
    expect(lastRead[1]?.headers).toMatchObject({
      Authorization: `Bearer token-${provider.id}`,
    });
  });
});
