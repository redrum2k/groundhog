import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  encodeUpload,
  MAX_UPLOAD_BYTES,
  prepareMutation,
  request,
  retryable,
  sendMutation,
} from "../lib/api";

afterEach(() => vi.unstubAllGlobals());
describe("explicit mutation requests", () => {
  it("retries the exact body, idempotency key and expected revision", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network lost"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: "run-1" })));
    vi.stubGlobal("fetch", fetcher);
    const mutation = prepareMutation(
      "/orders/order-1/commands",
      {
        verb: "answer",
        issue_id: "issue-1",
        question_id: "q-1",
        text: "The exact answer",
      },
      "Answer",
      12,
    );
    await expect(sendMutation(mutation, "session-token")).rejects.toThrow(
      "network lost",
    );
    await sendMutation(mutation, "session-token");
    expect(fetcher.mock.calls[0][1].body).toBe(fetcher.mock.calls[1][1].body);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toMatchObject({
      expected_revision: 12,
      question_id: "q-1",
      issue_id: "issue-1",
    });
    expect(fetcher.mock.calls[0][1].headers.Authorization).toBe(
      "Bearer session-token",
    );
    expect(JSON.parse(mutation.body)).not.toHaveProperty("role");
  });
  it("does not treat conflicts or authorization rejection as retryable", () => {
    expect(retryable(new ApiError(409, "stale"))).toBe(false);
    expect(retryable(new ApiError(403, "forbidden"))).toBe(false);
    expect(retryable(new ApiError(503, "unavailable"))).toBe(true);
  });
  it("propagates backend error detail without silently resubmitting", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: "revision stale" }), {
          status: 409,
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    await expect(request("/orders/order-1", "token")).rejects.toThrow(
      "409: revision stale",
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("bounds uploads before reading their bytes", async () => {
    const arrayBuffer = vi.fn();
    await expect(
      encodeUpload({
        size: MAX_UPLOAD_BYTES + 1,
        arrayBuffer,
      } as unknown as File),
    ).rejects.toThrow("2 MiB");
    expect(arrayBuffer).not.toHaveBeenCalled();
  });
});
