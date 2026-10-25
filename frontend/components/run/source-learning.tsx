"use client";

import { useEffect, useRef, useState } from "react";
import type { LearningResult, LearningState, ReviewView } from "../../lib/source_learning.generated";
import { jsonRequest, RunError } from "../../lib/run/live";
import styles from "./source-learning.module.css";

export default function SourceLearning({ openRun }: { openRun: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<LearningState>();
  const [error, setError] = useState<string>();
  const [disabled, setDisabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("");
  const [refresh, setRefresh] = useState(0);
  const alive = useRef(true);
  const pending = useRef<{ fingerprint: string; key: string } | undefined>(undefined);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await jsonRequest<LearningState>("/source-learning/state", undefined, undefined, abort.signal);
        if (abort.signal.aborted) return;
        setState(result);
        setDisabled(false);
      } catch (err) {
        if (abort.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Learning state unavailable");
        if (err instanceof RunError && err.status === 503 && err.message === "controlled local source learning is not enabled") {
          setState(undefined);
          setDisabled(true);
          return; // Disabled is a capability result, not a transient polling error.
        }
      }
      if (!abort.signal.aborted) timer = setTimeout(poll, 1000);
    };
    void poll();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [refresh]);
  const command = async (action: string, payload: Record<string, unknown>) => {
    if (busy) return;
    const fingerprint = JSON.stringify([action, payload]);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
    setBusy(true); setError(undefined);
    try {
      await jsonRequest<LearningResult>(`/source-learning/${action}`, { ...payload, idempotency_key: pending.current.key });
      if (!alive.current) return;
      pending.current = undefined;
      setRefresh(value => value + 1);
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "Learning command failed");
        setRefresh(value => value + 1); // Refetch 409s; never silently approve a changed target.
      }
    } finally { if (alive.current) setBusy(false); }
  };
  const upload = () => {
    try { void command("sources", JSON.parse(source)); }
    catch { setError("That isn't a valid source bundle. Paste the bundle's JSON."); }
  };
  const unresolved = state?.reviews?.filter(review => review.actionable && !review.resolved) ?? [];
  const history = state?.reviews?.filter(review => !review.actionable || review.resolved) ?? [];
  // the mode is the backend's own statement of what is simulated; any other mode shows its disclosure as sent
  const disclosure = state && (state.mode ?? "controlled_local_mock") === "controlled_local_mock"
    ? "The data sources are synthetic, the source owner and the controller are simulated people, and no real money moves."
    : state?.disclosure;
  return <div className={styles.root}>
    <button type="button" className="btn" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {state?.active_current ? "Learning active" : "Source learning"}{unresolved.length ? ` (${unresolved.length} to answer)` : ""}
    </button>
    {open && <section className={styles.panel} aria-label="Persistent source learning">
      <header><div><span className="faint">Local demo</span><h2>Learning from source owners</h2></div>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Close</button></header>
      <p>{disabled ? "Learning is turned off on this backend." : disclosure ?? "Connecting…"}</p>
      {disabled && <button type="button" className="btn" onClick={() => { setError(undefined); setRefresh(value => value + 1); }}>Check again</button>}
      <p><strong>{state?.active_current ? "A learned procedure is on" : state?.active_version ? "Paused: the code changed, so the procedure has to be tested again" : "Nothing learned yet"}</strong><br />
        <small>Learning never changes what a customer agreed to: consent, scope, prices and payment permissions stay as they were.</small></p>
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {state?.active_version && <details><summary>Active version</summary><code>{state.active_version}</code></details>}
      <details><summary>Add a new synthetic source</summary>
        <label>Source bundle JSON<textarea aria-label="Source bundle JSON" value={source} onChange={event => setSource(event.target.value)} rows={5} /></label>
        <button type="button" className="btn" disabled={busy || !state?.enabled || !source.trim()} onClick={upload}>Add source</button>
        <p>Then start a request as usual.</p>
      </details>
      <h3>Questions for the source owner</h3>
      {!unresolved.length && <p>No open questions.</p>}
      {unresolved.map(review => <OwnerReview key={review.encounter_id} review={review} busy={busy} command={command} openRun={openRun} />)}
      {!!history.length && <details><summary>Answered questions</summary>{history.map(review => <OwnerReview key={review.encounter_id} review={review} busy={busy} command={command} openRun={openRun} />)}</details>}
      <h3>Turn answers into a procedure</h3>
      <button type="button" className="btn" disabled={busy || !state?.bundle_id} onClick={() => void command("propose", { target_id: state?.bundle_id })}>Propose a procedure</button>
      {state?.candidates?.map(candidate => <article key={candidate.id}>
        <p>Built from {candidate.component_ids.length} evidence-backed parts. Status: {candidate.status.toLowerCase()}.</p>
        <details><summary>IDs</summary><code>{candidate.id}</code>{candidate.component_ids.map(id => <code key={id}>{id}</code>)}</details>
        <button type="button" className="btn" disabled={busy} onClick={() => void command("qualify", { target_id: candidate.id })}>Test on fresh cases</button>
        <button type="button" className="btn" disabled={busy || candidate.status !== "QUALIFIED"} onClick={() => void command("approve", { target_id: candidate.id })}>Approve as controller</button>
      </article>)}
      {state?.qualification && <article aria-label="Qualification results">
        <h3>{state.qualification.passed ? "Passed on fresh cases" : "Failed on fresh cases"}</h3>
        <p>{state.qualification.correct_both} of {state.qualification.cases} cases checked byte for byte, with and without the procedure.</p>
        <p>Reviews needed: {state.qualification.baseline_reviews} → {state.qualification.candidate_reviews}.<br />
          Machine steps: {state.qualification.baseline_operations} → {state.qualification.candidate_operations}.</p>
        <small>These are fresh engineering test cases, not an independent human evaluation or a measured saving in work.</small>
      </article>}
      {state?.versions?.map(version => <article key={version.id}>
        <p>Approved version. Status: {version.status.toLowerCase()}.</p><code>{version.id}</code>
        {version.status === "APPROVED" && <button type="button" className="btn solid" disabled={busy} onClick={() => void command("activate", { target_id: version.id })}>Turn on as controller</button>}
        {state.active_version === version.id && <button type="button" className="btn" disabled={busy} onClick={() => void command("revoke", { target_id: version.id })}>Turn off as controller</button>}
      </article>)}
      <h3>Activity</h3>
      {!state?.attempts?.some(attempt => attempt.active_version) && !state?.events?.length && <p>Nothing yet.</p>}
      {state?.attempts?.filter(attempt => attempt.active_version).map(attempt => <article key={attempt.id}>
        <strong>Same input, with and without learning</strong>
        <p>Reviews needed: {attempt.baseline_reviews} → {attempt.internal_reviews}.<br />
          Machine steps: {attempt.baseline_operations} → {attempt.machine_operations}.</p>
        <button type="button" className="btn" onClick={() => openRun(attempt.request_id)}>Open this order</button>
        <details><summary>Source hashes</summary>{attempt.source_hashes?.map(hash => <code key={hash}>{hash}</code>)}</details>
      </article>)}
      <ol className={styles.events}>{state?.events?.map(event => <li key={event.id}>
        <strong>{event.kind.replaceAll("_", " ")}</strong><p>{event.text}</p>
        <small>{event.actor}, {new Date(event.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</small>
        {event.request_id && <button type="button" className="btn" onClick={() => openRun(event.request_id!)}>Open order</button>}
        <details><summary>Evidence IDs</summary>{event.evidence_ids?.map(id => <code key={id}>{id}</code>)}</details>
      </li>)}</ol>
    </section>}
  </div>;
}

const REASONS: Record<string, string> = { ambiguous_source_definition: "The source doesn't say which column counts unique adults." };

function OwnerReview({ review, busy, command, openRun }: {
  review: ReviewView; busy: boolean;
  command: (action: string, payload: Record<string, unknown>) => Promise<void>;
  openRun: (id: string) => void;
}) {
  const [column, setColumn] = useState("");
  const [explanation, setExplanation] = useState("");
  return <article>
    <strong>{review.source_family}</strong><p>{REASONS[review.reason] ?? review.reason.replaceAll("_", " ")}</p>
    {review.review_status && <p>Status: {review.review_status}</p>}
    <details><summary>Source and authority hashes</summary><code>{review.source_sha256}</code><code>{review.authority_sha256}</code><code>{review.encounter_id}</code></details>
    <button type="button" className="btn" onClick={() => openRun(review.request_id)}>Open order</button>
    {review.actionable && !review.resolved && review.reason === "ambiguous_source_definition" && <>
      <label>Which column counts unique adults?<select aria-label={`Count column for ${review.source_family}`} value={column} onChange={event => setColumn(event.target.value)}>
        <option value="">Choose a column</option>{review.columns.map(value => <option key={value} value={value}>{value}</option>)}
      </select></label>
      <label>Why, in the source owner&apos;s words<textarea aria-label={`Owner explanation for ${review.source_family}`} value={explanation} onChange={event => setExplanation(event.target.value)} rows={2} /></label>
      <button type="button" className="btn" disabled={busy || !column || !explanation.trim()} onClick={() => void command("resolve", { encounter_id: review.encounter_id, column, explanation, applicability: "source_edition" })}>Answer as source owner</button>
      <small>You are answering as a simulated source owner. The answer applies only to this source&apos;s current schema and authority.</small>
    </>}
  </article>;
}
