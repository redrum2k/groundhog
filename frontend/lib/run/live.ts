"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { RunCreated, RunPage } from "../runs.generated";
import type { RunEvent } from "./contract";

const SESSION = "datumco.live-run.v1";
export const LIVE_API = "/api/live";
export class RunError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function jsonRequest<T>(path: string, body?: unknown, key?: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(LIVE_API + path, {method: body === undefined ? "GET" : "POST", signal, cache:"no-store", headers: {"Content-Type":"application/json", ...(key ? {"Idempotency-Key":key} : {})}, body:body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new RunError(response.status, typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`);
  return data as T;
}
export function mergeEvents(previous: RunEvent[], next: RunEvent[]): RunEvent[] {
  return [...new Map([...previous, ...next].map(e => [e.seq, e])).values()].sort((a,b) => a.seq-b.seq);
}
export function useLiveRun() {
  const [id, setId] = useState<string>();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [page, setPage] = useState<RunPage>();
  const [error, setError] = useState<string>();
  const [pollError, setPollError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  const identity = useRef(0);
  const displayedRun = useRef<string | undefined>(undefined);
  const pending = useRef<{fingerprint:string;key:string} | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    const turn = identity.current;
    const abort = new AbortController();
    try {
      const saved = JSON.parse(localStorage.getItem(SESSION) ?? "null");
      if (saved?.id) setId(saved.id);
      else if (saved?.key && saved?.prompt) {
        setBusy(true);
        void jsonRequest<RunCreated>("/runs", {prompt:saved.prompt,corpus_id:"sf-aggregate-v1"}, saved.key, abort.signal)
          .then(created => { if (!cancelled && turn === identity.current) {localStorage.setItem(SESSION,JSON.stringify({id:created.id}));setId(created.id);} })
          .catch(err => {if(!cancelled && turn === identity.current)setError(err instanceof Error?err.message:"Creation could not resume");})
          .finally(()=>{if(!cancelled && turn === identity.current)setBusy(false);});
      }
    } catch { setError("Saved run could not be read. Start a new run deliberately."); }
    return ()=>{cancelled=true;abort.abort();};
  }, []);
  useEffect(() => {
    const turn = ++generation.current;
    const abort = new AbortController();
    if (displayedRun.current !== id) {
      displayedRun.current = id;
      setEvents([]); setPage(undefined);
    }
    setRefreshing(!!id);
    setPollError(undefined);
    if (!id) return () => abort.abort();
    let cursor = 0;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await jsonRequest<RunPage>(`/runs/${encodeURIComponent(id)}/events?after=${cursor}`, undefined, undefined, abort.signal);
        if (turn !== generation.current || abort.signal.aborted) return;
        if (result.next_after < cursor || result.events.some(e => e.seq <= cursor)) throw new Error("Invalid event cursor; reload the run.");
        cursor = result.next_after;
        setEvents(prev => mergeEvents(prev, result.events));
        if (result.caught_up) setPage(result);
        setRefreshing(!result.caught_up);
        setPollError(undefined);
        timer = setTimeout(poll, result.caught_up ? result.poll_after_ms ?? 1000 : 0);
      } catch (err) {
        if (turn !== generation.current || abort.signal.aborted) return;
        // Keep the last confirmed review and decision visible, but disable mutations
        // until current permissions are available again.
        setRefreshing(true);
        setPollError(err instanceof Error ? err.message : "Backend unavailable");
        timer = setTimeout(poll, 1000);
      }
    };
    void poll();
    return () => { abort.abort(); clearTimeout(timer); generation.current++; };
  }, [id, refresh]);
  const resume = useCallback((run: string) => {
    identity.current++;
    generation.current++;
    localStorage.setItem(SESSION, JSON.stringify({id:run}));
    if (displayedRun.current !== run) {setEvents([]);setPage(undefined);}
    setError(undefined); setBusy(false); setRefreshing(true); setId(run); setRefresh(n=>n+1);
  }, []);
  const start = async (prompt: string) => {
    setBusy(true); setError(undefined);
    const turn = ++identity.current;
    try {
      const saved = JSON.parse(localStorage.getItem(SESSION) ?? "null");
      const key = saved?.prompt === prompt && !saved.id ? saved.key : crypto.randomUUID();
      localStorage.setItem(SESSION, JSON.stringify({key,prompt}));
      const created = await jsonRequest<RunCreated>("/runs", {prompt,corpus_id:"sf-aggregate-v1"}, key);
      if (turn === identity.current) resume(created.id);
    } catch (err) { if (turn === identity.current) setError(err instanceof Error ? err.message : "Creation failed"); }
    finally { if (turn === identity.current) setBusy(false); }
  };
  const command = async <T,>(path: string, payload: Record<string, unknown>, legacy = false): Promise<T | undefined> => {
    if (busy || refreshing) return;
    const turn = generation.current;
    const fingerprint = JSON.stringify([id,path,payload]);
    if (pending.current?.fingerprint !== fingerprint) pending.current = {fingerprint,key:crypto.randomUUID()};
    const key = pending.current.key;
    setBusy(true); setError(undefined);
    try {
      const result = await jsonRequest<T>(path, legacy ? {...payload,idempotency_key:key} : payload, key);
      if (turn !== generation.current) return;
      pending.current = undefined; setRefreshing(true); setRefresh(n=>n+1);
      return result;
    } catch (err) {
      if (turn !== generation.current) return;
      if (err instanceof RunError && err.status === 409) {
        pending.current = undefined; setRefreshing(true); setRefresh(n=>n+1);
        setError("The run changed. Refreshed evidence and permissions; review them and click again. " + err.message);
      } else setError(err instanceof Error ? err.message : "Command failed");
    } finally { if (turn === generation.current) setBusy(false); }
  };
  return {id,events,page,error:pollError ?? error,busy:busy || refreshing,start,resume,command, newRun:()=>{identity.current++;generation.current++;localStorage.removeItem(SESSION);pending.current=undefined;setId(undefined);setPage(undefined);setEvents([]);setBusy(false);setRefreshing(false);setError(undefined);}, retry:()=>{setError(undefined);setRefreshing(!!id);setRefresh(n=>n+1);}};
}
