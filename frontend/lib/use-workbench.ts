"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Actor, Event, OrderView } from "./jobflow.generated";
import {
  ApiError,
  request,
  restoreSession,
  retryable,
  saveSession,
  sendMutation,
  type PreparedMutation,
  type Session,
} from "./api";
import { mergeEvents, mergeSnapshot } from "./projection";

export function useWorkbench() {
  const [actors, setActors] = useState<Actor[]>([]);
  const [session, setSession] = useState<Session>();
  const [orders, setOrders] = useState<OrderView[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [order, setOrder] = useState<OrderView>();
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState<PreparedMutation>();
  const [refreshKey, setRefreshKey] = useState(0);
  const generation = useRef(0);
  const sessionGeneration = useRef(0);
  const inFlight = useRef(false);
  const currentId = useRef(selectedId);
  currentId.current = selectedId;
  const refresh = useCallback(() => setRefreshKey((n) => n + 1), []);

  useEffect(() => {
    setSession(restoreSession());
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    request<Actor[]>("/actors", undefined, { signal: controller.signal })
      .then(setActors)
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(`Local demo identities unavailable. ${e.message}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  const switchSession = async (actorId: string) => {
    if (inFlight.current || failed) return;
    const ticket = ++sessionGeneration.current;
    ++generation.current;
    setSession(undefined);
    saveSession();
    setOrders([]);
    setOrder(undefined);
    setSelectedId(undefined);
    setEvents([]);
    setFailed(undefined);
    setError(undefined);
    setNotice(undefined);
    setLoading(true);
    try {
      const next = await request<Session>("/sessions", undefined, {
        method: "POST",
        body: JSON.stringify({ actor_id: actorId }),
      });
      if (ticket !== sessionGeneration.current) return;
      saveSession(next);
      setSession(next);
    } catch (e) {
      if (ticket === sessionGeneration.current) setError((e as Error).message);
    } finally {
      if (ticket === sessionGeneration.current) setLoading(false);
    }
  };

  useEffect(() => {
    if (!session) return;
    const controller = new AbortController();
    setLoading(true);
    request<OrderView[]>("/orders", session.token, {
      signal: controller.signal,
    })
      .then((next) => {
        if (controller.signal.aborted) return;
        setOrders((old) =>
          next.map((snapshot) =>
            mergeSnapshot(
              old.find((o) => o.id === snapshot.id),
              snapshot,
            ),
          ),
        );
        setSelectedId((id) =>
          next.some((o) => o.id === id) ? id : next[0]?.id,
        );
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [session, refreshKey]);

  useEffect(() => {
    const ticket = ++generation.current;
    setEvents([]);
    if (!session || !selectedId) {
      setOrder(undefined);
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let cursor = 0;
    setLoading(true);
    const poll = async () => {
      try {
        const [snapshot, incoming] = await Promise.all([
          request<OrderView>(
            `/orders/${encodeURIComponent(selectedId)}`,
            session.token,
            { signal: controller.signal },
          ),
          request<Event[]>(
            `/orders/${encodeURIComponent(selectedId)}/events?after=${cursor}`,
            session.token,
            { signal: controller.signal },
          ),
        ]);
        if (ticket !== generation.current || controller.signal.aborted) return;
        setOrder((old) => mergeSnapshot(old, snapshot));
        setOrders((old) =>
          old.map((o) =>
            o.id === snapshot.id ? mergeSnapshot(o, snapshot) : o,
          ),
        );
        setEvents((old) => mergeEvents(old, incoming, selectedId));
        cursor = Math.max(cursor, ...incoming.map((e) => e.sequence));
      } catch (e) {
        if (ticket === generation.current && !controller.signal.aborted)
          setError(`Refresh failed. ${(e as Error).message}`);
      } finally {
        if (ticket === generation.current && !controller.signal.aborted) {
          setLoading(false);
          timer = setTimeout(poll, 2500);
        }
      }
    };
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [session, selectedId, refreshKey]);

  const selectOrder = (id: string) => {
    if (inFlight.current || failed || id === selectedId) return;
    ++generation.current;
    setOrder(undefined);
    setSelectedId(id);
    setEvents([]);
    setFailed(undefined);
    setError(undefined);
    setNotice(undefined);
  };
  const mutate = async (prepared: PreparedMutation) => {
    if (!session || inFlight.current) return false;
    if (failed && failed !== prepared) {
      setError(
        "The previous request has an uncertain outcome. Retry that exact request before starting another mutation.",
      );
      return false;
    }
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    setFailed(undefined);
    const ticket = sessionGeneration.current;
    const orderId = currentId.current;
    try {
      const result = await sendMutation(prepared, session.token);
      if (ticket !== sessionGeneration.current || orderId !== currentId.current)
        return false;
      if ("revision" in result) {
        setOrder((old) => mergeSnapshot(old, result));
        setSelectedId(result.id);
        setOrders((old) =>
          old.some((o) => o.id === result.id)
            ? old.map((o) =>
                o.id === result.id ? mergeSnapshot(o, result) : o,
              )
            : [...old, result],
        );
      }
      setNotice(
        "run_id" in result
          ? `Investigation queued · ${result.run_id}. Results will appear when persisted.`
          : `${prepared.label} recorded. Backend state refreshed.`,
      );
      refresh();
      return true;
    } catch (e) {
      if (ticket !== sessionGeneration.current) return false;
      if (e instanceof ApiError && e.status === 409) {
        setError(
          "409 — State or authorization changed. Refreshing the case. Review the latest evidence before making a new decision; this request will not be resubmitted.",
        );
        refresh();
      } else {
        setError((e as Error).message);
        if (retryable(e)) setFailed(prepared);
      }
      return false;
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };
  return {
    actors,
    session,
    orders,
    order,
    events,
    selectedId,
    error,
    notice,
    busy,
    loading,
    failed,
    refresh,
    switchSession,
    selectOrder,
    mutate,
    dismiss: () => {
      setError(undefined);
      setNotice(undefined);
    },
  };
}
