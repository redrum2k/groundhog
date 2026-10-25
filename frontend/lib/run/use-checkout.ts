"use client";
import { useEffect, useRef, useState } from "react";
import type { CanvasBinding, Quote } from "../runs.generated";
import { checkout, type CheckoutStage } from "./checkout";
import { RunError } from "./live";
import { browserWallet } from "./wallet";

export function useCheckout(runId: string | undefined, refresh: () => void) {
  const active = useRef<AbortController | undefined>(undefined);
  const [stage, setStage] = useState<CheckoutStage>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    setStage(undefined);
    setError(undefined);
    return () => { active.current?.abort(); active.current = undefined; };
  }, [runId]);

  async function pay(quote: Quote, binding?: CanvasBinding | null) {
    if (active.current || !runId) return;
    const controller = new AbortController();
    active.current = controller;
    setError(undefined);
    try {
      await checkout({runId, quote, binding, wallet: browserWallet(), signal: controller.signal, progress: setStage});
      return !controller.signal.aborted;
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof RunError && err.status === 409
        ? "The order changed. Review the refreshed payment status before trying again."
        : err instanceof Error ? err.message : "Payment could not be submitted. Check its status before retrying.");
      return false;
    } finally {
      if (!controller.signal.aborted) {
        active.current = undefined;
        setStage(undefined);
        refresh();
      }
    }
  }

  return {pay, stage, error, clearError: () => setError(undefined)};
}
