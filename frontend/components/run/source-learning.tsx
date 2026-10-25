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
    catch { setError("Supply a valid synthetic source-bundle JSON document."); }
  };
  const unresolved = state?.reviews?.filter(review => review.actionable && !review.resolved) ?? [];
  const history = state?.reviews?.filter(review => !review.actionable || review.resolved) ?? [];
  return <div className={styles.root}>
    <button type="button" className="btn" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {state?.active_current ? "Learning active" : "Source learning"}{unresolved.length ? ` · ${unresolved.length} reviews` : ""}
    </button>
    {open && <section className={styles.panel} aria-label="Persistent source learning">
      <header><div><span className="faint">Controlled local demonstration</span><h2>Learning from human interventions</h2></div>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Close learning</button></header>
      <p>{disabled ? "Source learning is disabled for this backend." : state?.disclosure ?? "Connecting to the running application…"}</p>
      {disabled && <button type="button" className="btn" onClick={() => { setError(undefined); setRefresh(value => value + 1); }}>Check learning availability</button>}
      <p><strong>{state?.active_current ? "Approved learning is enabled" : state?.active_version ? "Requalification required after code change" : "No procedure active yet"}</strong><br />
        <small>Customer consent, agreed scope, prices and payment permissions never change.</small></p>
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {state?.active_version && <details><summary>Active version</summary><code>{state.active_version}</code></details>}
      <details><summary>Supply new synthetic source bytes</summary>
        <label>Source bundle JSON<textarea aria-label="Source bundle JSON" value={source} onChange={event => setSource(event.target.value)} rows={5} /></label>
        <button type="button" className="btn" disabled={busy || !state?.enabled || !source.trim()} onClick={upload}>Receive source bundle</button>
        <p>Then start an ordinary brokerage request using the existing Agreement panel.</p>
      </details>
      <h3>Source-owner reviews</h3>
      {!unresolved.length && <p>No unresolved source-owner review is recorded.</p>}
      {unresolved.map(review => <OwnerReview key={review.encounter_id} review={review} busy={busy} command={command} openRun={openRun} />)}
      {!!history.length && <details><summary>Review history</summary>{history.map(review => <OwnerReview key={review.encounter_id} review={review} busy={busy} command={command} openRun={openRun} />)}</details>}
      <h3>Learn and qualify</h3>
      <button type="button" className="btn" disabled={busy || !state?.bundle_id} onClick={() => void command("propose", { target_id: state?.bundle_id })}>Derive composed procedure</button>
      {state?.candidates?.map(candidate => <article key={candidate.id}>
        <p>{candidate.component_ids.length} evidenced components · {candidate.status}</p>
        <details><summary>Candidate / evidence IDs</summary><code>{candidate.id}</code>{candidate.component_ids.map(id => <code key={id}>{id}</code>)}</details>
        <button type="button" className="btn" disabled={busy} onClick={() => void command("qualify", { target_id: candidate.id })}>Qualify on fresh cases</button>
        <button type="button" className="btn" disabled={busy || candidate.status !== "QUALIFIED"} onClick={() => void command("approve", { target_id: candidate.id })}>Controller: approve</button>
      </article>)}
      {state?.qualification && <article aria-label="Qualification results">
        <h3>{state.qualification.passed ? "Qualification passed" : "Qualification failed"}</h3>
        <p>{state.qualification.correct_both}/{state.qualification.cases} cases independently byte-verified for both arms.</p>
        <p>Internal reviews: {state.qualification.baseline_reviews} → {state.qualification.candidate_reviews}.<br />
          Machine operations: {state.qualification.baseline_operations} → {state.qualification.candidate_operations}.</p>
        <small>Fresh engineering cases; not independent human evaluation or measured labor savings.</small>
      </article>}
      {state?.versions?.map(version => <article key={version.id}>
        <p>Controller-approved version · {version.status}</p><code>{version.id}</code>
        {version.status === "APPROVED" && <button type="button" className="btn solid" disabled={busy} onClick={() => void command("activate", { target_id: version.id })}>Controller: activate learning</button>}
        {state.active_version === version.id && <button type="button" className="btn" disabled={busy} onClick={() => void command("revoke", { target_id: version.id })}>Controller: revoke learning</button>}
      </article>)}
      <h3>Actual application events</h3>
      {state?.attempts?.filter(attempt => attempt.active_version).map(attempt => <article key={attempt.id}>
        <strong>Same-byte stateless comparison</strong>
        <p>Internal reviews: {attempt.baseline_reviews} → {attempt.internal_reviews}.<br />
          Assessment operations: {attempt.baseline_operations} → {attempt.machine_operations}.</p>
        <button type="button" className="btn" onClick={() => openRun(attempt.request_id)}>Open compared order</button>
        <details><summary>Exact new source hashes</summary>{attempt.source_hashes?.map(hash => <code key={hash}>{hash}</code>)}</details>
      </article>)}
      <ol className={styles.events}>{state?.events?.map(event => <li key={event.id}>
        <strong>{event.kind.replaceAll("_", " ")}</strong><p>{event.text}</p>
        <small>{event.actor} · {event.created_at}</small>
        {event.request_id && <button type="button" className="btn" onClick={() => openRun(event.request_id!)}>Open order</button>}
        <details><summary>Evidence IDs</summary>{event.evidence_ids?.map(id => <code key={id}>{id}</code>)}</details>
      </li>)}</ol>
    </section>}
  </div>;
}

function OwnerReview({ review, busy, command, openRun }: {
  review: ReviewView; busy: boolean;
  command: (action: string, payload: Record<string, unknown>) => Promise<void>;
  openRun: (id: string) => void;
}) {
  const [column, setColumn] = useState("");
  const [explanation, setExplanation] = useState("");
  return <article>
    <strong>{review.source_family}</strong><p>{review.reason.replaceAll("_", " ")}</p>
    <p>Review status: {review.review_status}</p>
    <details><summary>Exact source / authority hashes</summary><code>{review.source_sha256}</code><code>{review.authority_sha256}</code><code>{review.encounter_id}</code></details>
    <button type="button" className="btn" onClick={() => openRun(review.request_id)}>Open order</button>
    {review.actionable && !review.resolved && review.reason === "ambiguous_source_definition" && <>
      <label>Unique-adult count column<select aria-label={`Count column for ${review.source_family}`} value={column} onChange={event => setColumn(event.target.value)}>
        <option value="">Choose from owner evidence</option>{review.columns.map(value => <option key={value} value={value}>{value}</option>)}
      </select></label>
      <label>Source-owner explanation<textarea aria-label={`Owner explanation for ${review.source_family}`} value={explanation} onChange={event => setExplanation(event.target.value)} rows={2} /></label>
      <button type="button" className="btn" disabled={busy || !column || !explanation.trim()} onClick={() => void command("resolve", { encounter_id: review.encounter_id, column, explanation, applicability: "source_edition" })}>Source owner: resolve</button>
      <small>This trusted local identity is explicitly simulated. Resolution applies only to this source schema and authority.</small>
    </>}
  </article>;
}
