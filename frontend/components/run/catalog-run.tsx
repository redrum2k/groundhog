"use client";

import { useEffect, useRef, useState } from "react";
import type { CatalogEvent, CatalogRunSummary, FundingPreparation, OrderView, Quote, RequestDraft, Source } from "../../lib/run.generated";
import { CATALOG_API, CatalogError, catalogCanvas, catalogNodes, catalogRequest, exactMoney, mergeCatalogEvents, pollCatalog } from "../../lib/run/catalog";
import Canvas from "./canvas";
import CatalogImprovement from "./catalog-improvement";
import { IcLogo, IcX } from "./icons";

const newKey = () => crypto.randomUUID();
const persistedRun = "objection.catalog.run";

export default function CatalogRun({ onRecorded }: { onRecorded: () => void }) {
  const [runId, setRunId] = useState("");
  const [events, setEvents] = useState<CatalogEvent[]>([]);
  const [runs, setRuns] = useState<CatalogRunSummary[]>([]);
  const [corpora, setCorpora] = useState<Record<string, Source[]>>({});
  const [corpus, setCorpus] = useState("");
  const [prompt, setPrompt] = useState("Find storage products with net unit weight under 2 kg and unit price no more than USD 40.");
  const [draft, setDraft] = useState<RequestDraft>();
  const [quote, setQuote] = useState<Quote>();
  const [answer, setAnswer] = useState("");
  const [preparation, setPreparation] = useState<FundingPreparation>();
  const [panel, setPanel] = useState<string | null>("clarify");
  const [overview, setOverview] = useState(false);
  const [replay, setReplay] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [serverTime, setServerTime] = useState("");
  const [reviewAction, setReviewAction] = useState<"request_evidence" | "release_authorization" | "propose_exception">("request_evidence");
  const [reviewReason, setReviewReason] = useState("");
  const [reviewEvidence, setReviewEvidence] = useState("0");
  // Keep a command's exact key/payload if the response is lost. Explicit retry
  // reuses it; stale 409s are never silently reauthorized.
  const retry = useRef<null | (() => Promise<void>)>(null);
  const cursor = useRef(0);
  const latest = events.at(-1), order = latest?.order;
  const payment = latest?.payment?.payment;
  const delivery = order?.deliveries?.at(-1);
  const reviewAssessments = [
    ...(order?.verification?.assessments ?? []),
    ...(order?.amendments ?? []).slice().reverse().flatMap(a => a.assessment ?? []),
    ...(order?.verification_history ?? []).slice().reverse().flatMap(v => v.assessments),
  ];
  const reviewCitations = [...new Map(reviewAssessments.flatMap(a => a.citations ?? []).map(c => [`${c.artifact_id}:${c.page}:${c.start}:${c.end}`, c])).values()];
  const view = catalogCanvas(latest);

  useEffect(() => {
    const saved = localStorage.getItem(persistedRun);
    if (saved) setRunId(saved);
    void catalogRequest<Record<string, Source[]>>("corpora").then(data => {
      setCorpora(data); setCorpus(Object.keys(data)[0] ?? "");
    }).catch(e => setError(String(e)));
    void catalogRequest<CatalogRunSummary[]>("runs").then(setRuns).catch(e => setError(String(e)));
  }, []);

  useEffect(() => {
    setEvents([]); cursor.current = 0;
    if (!runId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const batch = await pollCatalog(runId, cursor.current);
        if (cancelled) return;
        setEvents(prev => mergeCatalogEvents(prev, batch.events));
        cursor.current = batch.next_cursor; setServerTime(batch.server_time);
        // Drain pages even in read-only replay; never POST from this effect.
        if (!replay || batch.events.length === 100) timer = setTimeout(poll, batch.events.length === 100 ? 0 : batch.poll_after_ms ?? 2000);
      } catch (e) {
        if (!cancelled) { setError(String(e)); if (!replay) timer = setTimeout(poll, 2000); }
      }
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [runId, replay]);

  const refresh = async (id = runId) => {
    if (!id) return;
    const batch = await pollCatalog(id, id === runId ? cursor.current : 0);
    if (id !== runId) { setRunId(id); localStorage.setItem(persistedRun, id); return; }
    setEvents(prev => mergeCatalogEvents(prev, batch.events)); cursor.current = batch.next_cursor; setServerTime(batch.server_time);
  };
  const act = async (operation: () => Promise<void>, keep = true) => {
    setBusy(true); setError(""); if (keep) retry.current = operation;
    try { await operation(); retry.current = null; }
    catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof CatalogError && e.status < 500) retry.current = null;
      if (e instanceof CatalogError && e.status === 409) await refresh();
    } finally { setBusy(false); }
  };
  const command = () => {
    if (!latest) throw new Error("No authoritative order binding");
    return { expected_revision: latest.aggregate_revision, expected_binding: latest.binding, idempotency_key: newKey() };
  };
  const send = (suffix: string, extras: object = {}) => {
    const payload = { ...command(), ...extras };
    void act(async () => { await catalogRequest(`orders/${runId}/${suffix}`, payload); await refresh(); });
  };
  const work = () => void act(async () => { await catalogRequest(`worker/orders/${runId}/work`, {}); await refresh(); });
  const review = () => {
    const citation = reviewCitations[Number(reviewEvidence)];
    if (!citation || !reviewReason.trim()) return;
    const payload = { ...command(), action: reviewAction, reason: reviewReason, supporting_evidence: [citation] };
    void act(async () => { await catalogRequest(`reviewer/orders/${runId}/decisions`, payload); await refresh(); });
  };
  const openRun = (id: string) => { setDraft(undefined); setQuote(undefined); setPreparation(undefined); setRunId(id); localStorage.setItem(persistedRun, id); setPanel("produce"); };
  const newDraft = () => {
    const payload = { prompt, corpus_id: corpus, idempotency_key: newKey() };
    void act(async () => {
      const created = await catalogRequest<RequestDraft>("requests", payload);
      setDraft(created); setQuote(undefined); setPreparation(undefined); setRunId(""); setEvents([]); localStorage.removeItem(persistedRun); setPanel("clarify");
    });
  };
  const compile = () => {
    if (!draft) return;
    const id = draft.request_id, payload = { expected_revision: draft.revision ?? 1, idempotency_key: newKey() };
    void act(async () => { setDraft(await catalogRequest<RequestDraft>(`worker/requests/${id}/compile`, payload)); });
  };
  const clarify = () => {
    if (!draft?.question) return;
    const id = draft.request_id, payload = { expected_revision: draft.revision ?? 1, idempotency_key: newKey(), question_id: draft.question.question_id, text: answer };
    void act(async () => { setDraft(await catalogRequest<RequestDraft>(`requests/${id}/answers`, payload)); setAnswer(""); });
  };
  const requestQuote = () => {
    if (!draft) return;
    const id = draft.request_id, payload = { expected_revision: draft.revision ?? 1, idempotency_key: newKey() };
    void act(async () => { setQuote(await catalogRequest<Quote>(`requests/${id}/quotes`, payload)); });
  };
  const acceptQuote = () => {
    if (!quote) return;
    const payload = { quote_id: quote.quote_id, customer_actor: "customer:local-demo", idempotency_key: newKey() };
    void act(async () => { const result = await catalogRequest<OrderView>("quote-acceptance", payload); openRun(result.order.snapshot.order_id); setPanel("paid"); });
  };
  const prepare = () => {
    const payload = command();
    void act(async () => { setPreparation(await catalogRequest<FundingPreparation>(`orders/${runId}/funding-preparation`, payload)); });
  };
  const upload = async (file?: File) => {
    const request = order?.evidence_requests?.find(r => !r.answered);
    if (!file || !request) return;
    if (file.size > 2_000_000) { setError("PDF exceeds the 2 MB evidence limit"); return; }
    const bytes = new Uint8Array(await file.arrayBuffer());
    let encoded = ""; for (const byte of bytes) encoded += String.fromCharCode(byte);
    send("amendments", { evidence_request_id: request.request_id, actor: "customer:local-demo", reason: "Requested source evidence supplied for current review", relationship: "replacement_page", pdf_base64: btoa(encoded) });
  };
  const disabled = busy || replay;
  const artifact = (id: string, page?: number) => `${CATALOG_API}/orders/${runId}/artifacts/${id}${page ? `#page=${page}` : ""}`;
  const title = catalogNodes.find(n => n.id === panel)?.title ?? "Catalog order";
  const displayedQuote = quote ?? order?.snapshot.quote;

  return <div className="shell">
    <header className="top">
      <div className="brand"><span className="logo"><IcLogo /></span><div><div className="title">Catalog order <span className="faint">· {runId ? runId.slice(-12) : "New request"}</span></div><div className="seatline">Live backend · synthetic supplier corpus · mock finance</div></div></div>
      <div className="top-r"><button className="btn" onClick={onRecorded}>Recorded sample</button><span className="tag">{replay ? "Read-only saved events" : "Explicit commands only"}</span></div>
    </header>
    <div className="tools">
      <button className="btn" onClick={() => setPanel("clarify")}>New order</button>
      <button className="btn" onClick={() => setPanel("improve")}>Improve future work</button>
      <select aria-label="Saved catalog order" value={runs.some(r => r.run_id === runId) ? runId : ""} onChange={e => openRun(e.target.value)}><option value="" disabled>Open saved order</option>{runs.map(r => <option key={r.run_id} value={r.run_id}>{r.run_id.slice(-12)} · {r.state}</option>)}</select>
      <button className="btn" onClick={() => { setOverview(!overview); setPanel(null); }}>{overview ? "Follow order" : "Overview"}</button>
      <button className="btn" disabled={!runId} onClick={() => { setReplay(!replay); setPreparation(undefined); }}>{replay ? "Return to live" : "Read-only replay"}</button>
      <div className="spacer" /><span className="faint">{latest ? `Event ${latest.seq} · revision ${latest.aggregate_revision}` : "No accepted order"}</span>
    </div>
    <main className="stage">
      <Canvas nodes={catalogNodes} view={view} focus={{ kind: overview ? "overview" : "follow" }} panelOpen={!!panel} onNode={setPanel} quiet={overview} overlay={<div className={`caption${panel ? " shifted" : ""}`} aria-live="polite"><span className="cap-text">{error || (order ? `${order.order_state} · ${payment?.state ?? order.authorization.status}. ${order.error ?? ""}` : "Describe the work, inspect the quote, then explicitly accept." )}</span></div>} />
      {panel && <aside className="panel" aria-label={title}>
        <div className="panel-h"><div><div className="panel-t">{title}</div><div className="faint">{replay ? "Saved history — commands disabled" : "Authoritative catalog state"}</div></div><button className="sq" aria-label="Close panel" onClick={() => setPanel(null)}><IcX /></button></div>
        <div className="panel-b catalog-detail">
          {panel === "improve" && <CatalogImprovement corpus={order?.snapshot.quote.specification?.terms.corpus_id ?? corpus} replay={replay} />}
          {error && <div role="alert" className="catalog-note">{error}{retry.current && <button className="btn" disabled={busy} onClick={() => retry.current && void act(retry.current, false)}>Retry exact command</button>}</div>}
          {panel === "clarify" && <>
            <label>Provider corpus<select aria-label="Provider corpus" value={corpus} onChange={e => setCorpus(e.target.value)}>{Object.keys(corpora).map(id => <option key={id}>{id}</option>)}</select></label>
            <label>Requested work<textarea aria-label="Requested work" value={prompt} onChange={e => setPrompt(e.target.value)} /></label>
            <button className="btn solid" disabled={disabled || !corpus || !prompt} onClick={newDraft}>Create new draft</button>
            {draft && <section><p>Draft {draft.request_id.slice(-12)} · {draft.status} · revision {draft.revision}</p><p>Deadline: {draft.deadline}</p>
              {draft.status === "compiling" && <button className="btn" disabled={disabled} onClick={compile}>Compile draft · synthetic staff</button>}
              {draft.question && <><p>{draft.question.prompt}</p><input aria-label="Clarification answer" value={answer} onChange={e => setAnswer(e.target.value)} /><button className="btn" disabled={disabled || !answer} onClick={clarify}>Send answer</button></>}
              {draft.specification && <><p>{draft.specification.summary}</p>{draft.specification.limitations.map((l, i) => <p key={i} className="catalog-note">{l}</p>)}</>}
              {draft.status === "ready" && <button className="btn" disabled={disabled} onClick={requestQuote}>Request server quote</button>}
            </section>}
            {displayedQuote && <section><h3>Exact offered terms</h3><p>{displayedQuote.work_description}</p><p>{exactMoney(displayedQuote.amount)} · {displayedQuote.policy?.version} · review {displayedQuote.policy?.review_seconds} seconds</p><p>{displayedQuote.payment_terms?.amount_atomic} atomic {displayedQuote.payment_terms?.symbol} · {displayedQuote.payment_terms?.mode}</p><p>{displayedQuote.payment_terms?.settlement_terms}</p><p className="mono">Receiver {displayedQuote.payment_terms?.payment_info.receiver}<br />Operator {displayedQuote.payment_terms?.payment_info.operator}</p><p>Quote expires {displayedQuote.expires_at}</p><ul>{displayedQuote.specification.requirements.map(r => <li key={r.requirement_id}>{r.wording}</li>)}</ul>{quote && <button className="btn solid" disabled={disabled} onClick={acceptQuote}>Accept this quote · customer</button>}</section>}
          </>}
          {order && panel !== "clarify" && panel !== "improve" && <>
            <p className="catalog-note">Customer acceptance, funding, fulfillment and capture are separate. The platform operator applies accepted rules. Mock outcomes are not on-chain settlement.</p>
            {panel === "paid" && <><p>Payment: {payment?.state ?? order.authorization.status}</p><p>{payment?.terms.amount_atomic} atomic {payment?.terms.symbol} · {payment?.terms.mode}</p><p>Funding deadline: {payment ? new Date(Number(payment.terms.payment_info.pre_approval_expiry) * 1000).toISOString() : "unavailable"}</p>
              {payment?.state === "awaiting_signature" && <><button className="btn" disabled={disabled} onClick={prepare}>Prepare funding</button>{preparation && <button className="btn solid" disabled={disabled} onClick={() => send("funding-authorizations", { funding_attempt_id: preparation.funding_attempt_id, payment_hash: preparation.terms.payment_hash, simulate: true })}>Authorize mock funding · customer</button>}</>}
              {payment?.state === "funding_pending" && <button className="btn" disabled={disabled} onClick={() => void act(async () => { await catalogRequest("worker/payments/work", {}); await refresh(); })}>Confirm mock funding · synthetic operator</button>}
            </>}
            {(panel === "produce" || panel === "evidence") && <>
              {(order.jobs ?? []).map(job => <p key={job.job_id}>{job.kind} · {job.status} · attempts {job.attempts}{job.error && ` · ${job.error}`}</p>)}
              <button className="btn" disabled={disabled || !order.jobs?.some(j => j.status === "queued") || !order.authorization.receipt} onClick={work}>Execute queued work · synthetic staff</button>
              {(order.evidence_requests ?? []).map(r => <section key={r.request_id}><h3>Evidence request {r.round}</h3><p>{r.prompt}</p><p>{r.target_source.source_id} · edition {r.target_source.edition} · {r.answered ? "Answered" : "Pending"}</p><p>Deadline {r.deadline}</p>{!r.answered && <label>Requested PDF only<input aria-label="Evidence PDF" type="file" accept="application/pdf" disabled={disabled} onChange={e => void upload(e.target.files?.[0])} /></label>}</section>)}
              {(order.amendments ?? []).map(a => <p key={a.amendment_id}>Repair: {a.classification} · {a.assessment?.map(x => x.reason_code).join(", ")}</p>)}
            </>}
            {(panel === "review" || panel === "produce" || panel === "evidence" || panel === "human") && <>
              {(order.deliveries ?? []).map(d => <section key={d.version}><h3>Delivery {d.version}</h3><a className="cite" href={artifact(d.pdf.artifact_id)} target="_blank" rel="noreferrer">Inspect actual PDF</a> <a href={artifact(d.sidecar.artifact_id)} target="_blank" rel="noreferrer">Source-derived sidecar</a><p>Review closes {d.review_deadline}</p><p className="mono">SHA-256 {d.pdf.sha256}</p></section>)}
              {panel === "review" && delivery && <button className="btn solid" disabled={disabled || order.order_state !== "delivered"} onClick={() => send("acceptance")}>Accept current delivery · customer</button>}
              <h3>Source evidence and checks</h3>
              {!!order.verification_history?.length && <details><summary>Retained prior verification and failed output evidence</summary>{order.verification_history.map((v, i) => <section key={i}><p>{v.provider_defect ? "Established provider defect" : "Prior verification"} · {v.stage} · evidence revision {v.binding.evidence_revision}</p>{v.assessments.filter(a => a.result !== "PASS").map((a, j) => <p key={j}>{a.result} · {a.reason_code} · {a.explanation}{a.citations?.map((c, k) => <a className="cite" key={k} href={artifact(c.artifact_id, c.page)} target="_blank" rel="noreferrer">Inspect retained artifact, page {c.page}</a>)}</p>)}</section>)}</details>}
              {order.sources.map(s => <p key={`${s.source_id}:${s.version}`}><a href={artifact(s.artifact.artifact_id)} target="_blank" rel="noreferrer">{s.source_id} v{s.version} · {s.edition}</a><br /><span className="faint">{s.authority} · {s.effective_date}</span></p>)}
              {(order.verification?.assessments ?? []).map((a, i) => <section key={`${a.obligation_id}:${i}`}><p><strong>{a.result}</strong> · {a.reason_code}</p><p>{a.explanation}</p>{a.missing_facts?.map(f => <p key={f}>Missing: {f}</p>)}{a.citations?.map((c, j) => <a className="cite" key={j} href={artifact(c.artifact_id, c.page)} target="_blank" rel="noreferrer">Page {c.page}: {c.quote.slice(0, 110)}</a>)}</section>)}
            </>}
            {panel === "human" && <><h3>Held for responsible reviewer</h3><p>{order.error ?? "Required evidence or consent remains unresolved; no automatic override."}</p><p>Authority: {order.authority_state}. Financial state: {payment?.state}.</p><p>Company review, source acquisition and customer consent remain separate actions.</p>
              <p className="catalog-note">Synthetic local reviewer capability. No factual override or capture action is available. Releasing an uncaptured authorization is not a refund; an exception proposal still requires a new agreement.</p>
              <label>Reviewer action<select aria-label="Reviewer action" value={reviewAction} onChange={e => setReviewAction(e.target.value as typeof reviewAction)}><option value="request_evidence">Request evidence within existing bounds</option><option value="propose_exception">Propose negotiated exception only</option><option value="release_authorization">Release uncaptured authorization</option></select></label>
              <label>Supporting source citation<select aria-label="Reviewer supporting citation" value={reviewEvidence} onChange={e => setReviewEvidence(e.target.value)}>{reviewCitations.map((c, i) => <option key={i} value={String(i)}>Page {c.page}: {c.quote.slice(0, 90)}</option>)}</select></label>
              <label>Reviewer reason<textarea aria-label="Reviewer reason" value={reviewReason} onChange={e => setReviewReason(e.target.value)} /></label>
              <button className="btn" disabled={disabled || order.order_state !== "human_review" || !reviewReason.trim() || !reviewCitations[Number(reviewEvidence)]} onClick={review}>Record bound reviewer decision</button>
              {(order.decisions ?? []).map((d, i) => <p key={i}>{d.action} · {d.actor} · {d.reason}</p>)}
            </>}
            {panel === "captured" && <><h3>{payment?.state ?? "Unresolved payment state"}</h3><p>Delivery produced: {delivery ? "yes" : "no"}. Verified compliant: {order.verification?.passed ? "yes" : "no"}. Order closed: {order.order_state === "closed" ? "yes" : "no"}.</p>{(order.ledger ?? []).map(b => <p key={b.operation_id}>{b.kind} · {exactMoney(b.amount)} · {b.receipt.status} · {b.recorded_at}</p>)}{latest?.payment?.operations.map(o => <p key={o.operation_id}>{o.intent.action} · {o.state} · {o.error ?? ""}</p>)}</>}
            <details><summary>Authoritative binding and event</summary><pre>{JSON.stringify({ run_id: runId, event_id: latest?.event_id, revision: latest?.aggregate_revision, binding: latest?.binding, accepted_hash: latest?.accepted_snapshot_sha256, actor: latest?.actor, operation: latest?.operation, occurred_at: latest?.occurred_at, server_time: serverTime }, null, 2)}</pre></details>
          </>}
          {!order && panel !== "clarify" && panel !== "improve" && <p>No accepted catalog order. Create and explicitly accept a draft first.</p>}
        </div>
      </aside>}
    </main>
  </div>;
}
