"use client";

import { useEffect, useRef, useState } from "react";
import type { CatalogImprovementCommand, CatalogImprovementResult, CatalogImprovementView } from "../../lib/catalog_improvement.generated";
import { catalogRequest, CatalogError } from "../../lib/run/catalog";

export default function CatalogImprovement({ corpus, replay }: { corpus: string; replay: boolean }) {
  const [view, setView] = useState<CatalogImprovementView>();
  const [reason, setReason] = useState("Inspect the exact candidate, isolated probe and immutable source binding; preserve all accepted orders.");
  const [error, setError] = useState("");
  const [result, setResult] = useState<CatalogImprovementResult>();
  const [busy, setBusy] = useState(false);
  const retry = useRef<CatalogImprovementCommand | null>(null);
  const refresh = async () => setView(await catalogRequest<CatalogImprovementView>(`improvements/scopes/${encodeURIComponent(corpus)}`));
  useEffect(() => {
    let cancelled = false;
    if (corpus) void catalogRequest<CatalogImprovementView>(`improvements/scopes/${encodeURIComponent(corpus)}`).then(v => { if (!cancelled) setView(v); }).catch(e => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, [corpus]); // Read-only on navigation, refresh and replay.
  const execute = async (payload: CatalogImprovementCommand) => {
    setBusy(true); setError(""); retry.current = payload;
    const reviewer = ["approve", "activate", "revoke"].includes(payload.verb);
    try {
      const answer = await catalogRequest<CatalogImprovementResult>(`${reviewer ? "reviewer" : "worker"}/improvements/${reviewer ? "review" : "commands"}`, payload);
      setResult(answer); retry.current = null; await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof CatalogError && e.status < 500) retry.current = null;
      if (e instanceof CatalogError && e.status === 409) await refresh();
    } finally { setBusy(false); }
  };
  const send = (verb: CatalogImprovementCommand["verb"], fields: Partial<CatalogImprovementCommand> = {}) => {
    if (!view) return;
    void execute({ verb, corpus_id: corpus, expected_active_version: view.active_version, reason,
      idempotency_key: crypto.randomUUID(), ...fields });
  };
  const records = view?.records ?? [];
  const incidents = records.filter(r => r.kind === "catalog_incident");
  const patches = records.filter(r => r.kind === "catalog_patch");
  const generated = records.filter(r => r.kind === "catalog_generation");
  const selectedIncidents = incidents.slice(-8).map(r => r.id) as CatalogImprovementCommand["incident_ids"];
  const disabled = busy || replay || !reason.trim();
  return <section aria-label="Prospective catalog improvement">
    <p className="catalog-note">Actual model proposals are evidence, not approval. Only an exact tested candidate can be separately approved and activated for future drafts. Accepted orders retain their pinned procedure. Reviewer controls here are a synthetic local role, not a production human audit.</p>
    <p>Application model: {view?.model_generation ?? "Loading"}. Active procedure: <span className="mono">{view?.active_version}</span></p>
    <button className="btn" disabled={busy} onClick={() => void refresh().catch(e => setError(String(e)))}>Refresh saved improvement records</button>
    <label>Review or generation reason<textarea aria-label="Improvement reason" value={reason} onChange={e => setReason(e.target.value)} /></label>
    {error && <p role="alert">{error}{retry.current && <button className="btn" disabled={disabled} onClick={() => retry.current && void execute(retry.current)}>Retry exact improvement command</button>}</p>}
    {result && <p role="status">{result.status}: {result.reason ?? result.version_id ?? result.probe_id}</p>}
    <h3>Observed incidents ({incidents.length})</h3>
    {incidents.map(r => <details key={r.id}><summary>{r.id}</summary><pre>{JSON.stringify(r.data, null, 2)}</pre></details>)}
    <button className="btn" disabled={disabled || !incidents.length || view?.model_generation !== "CONFIGURED" || generated.length >= 2} onClick={() => send("propose", { incident_ids: selectedIncidents, cycle: generated.length ? 2 : 1 })}>Generate genuine model proposal</button>
    {patches.map(patch => {
      const probe = records.filter(r => r.kind === "catalog_probe" && r.data.patch_id === patch.id).at(-1);
      const report = probe?.data.report as { promotion_eligible?: boolean; violations?: unknown[]; comparison_claim?: string; changed_cases?: string[] } | undefined;
      const status = view?.statuses[patch.id];
      const approved = records.some(r => r.kind === "catalog_approval" && r.data.patch_id === patch.id && r.data.probe_id === probe?.id);
      return <section key={patch.id} className="catalog-note"><h3>Candidate · {status ?? "recorded"}</h3><p className="mono">{patch.id}</p><p>Generation mode: {String(patch.data.mode)} · {String(patch.data.model)}</p><pre>{JSON.stringify(patch.data.proposal, null, 2)}</pre>
        <button className="btn" disabled={disabled} onClick={() => send("probe", { patch_id: patch.id })}>Validate candidate in isolated workflows</button>
        {probe && <><h4>Isolated probe</h4><p>{report?.comparison_claim}</p><p>Promotion eligible: {String(report?.promotion_eligible)}. Changed development cases: {report?.changed_cases?.join(", ") || "none"}. Violations: {report?.violations?.length ?? "unknown"}.</p><p className="mono">Source {String(probe.data.implementation_sha256)}</p>
          <button className="btn" disabled={disabled || !report?.promotion_eligible || approved} onClick={() => send("approve", { patch_id: patch.id, probe_id: probe.id })}>Approve exact tested candidate · reviewer</button>
          <button className="btn solid" disabled={disabled || !report?.promotion_eligible || !approved || status === "ACTIVE"} onClick={() => send("activate", { patch_id: patch.id, probe_id: probe.id })}>Activate for future drafts · reviewer</button>
          <details><summary>Full retained probe evidence</summary><pre>{JSON.stringify(probe.data, null, 2)}</pre></details></>}
      </section>;
    })}
    {view && view.active_version !== "catalog-static-v1" && <button className="btn" disabled={disabled} onClick={() => send("revoke", { version_id: view.active_version })}>Revoke active procedure for future drafts · reviewer</button>}
    <details><summary>Raw generation, rejected proposals and lifecycle evidence</summary><pre>{JSON.stringify(records.filter(r => r.kind !== "catalog_probe"), null, 2)}</pre></details>
  </section>;
}
