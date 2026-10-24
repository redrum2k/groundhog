"use client";
import { useEffect, useRef, useState } from "react";
import type { Job, OrderView } from "../lib/jobflow.generated";
import { prepareMutation, type CommandInput } from "../lib/api";
import {
  acceptableJobs,
  activeDispute,
  can,
  jobTone,
  money,
  nextInTraversal,
  originalProgress,
  recoverableJobs,
  unresolvedIds,
  words,
  type Tone,
} from "../lib/projection";
import { useWorkbench } from "../lib/use-workbench";
import { Badge, Button } from "./ui";
import { Courier } from "./courier";
import { EvidenceDrawer, CitationList, SourceCard } from "./evidence";
import { FinanceDrawer } from "./finance";
import { IssuePanel } from "./issue-panel";
import { ChangeOrders } from "./change-orders";

const toneLabels: Record<Tone, string> = {
  green: "Validated",
  red: "Failed",
  orange: "Disputed",
  blue: "Pending",
};
function Axes({ job }: { job: Job }) {
  return (
    <div className="axes">
      <Badge
        tone={
          job.processing === "FAILED"
            ? "red"
            : job.processing === "VALIDATED"
              ? "green"
              : "blue"
        }
      >
        Processing: {words(job.processing)}
      </Badge>
      <Badge tone={activeDispute(job) ? "orange" : "neutral"}>
        Dispute: {words(job.dispute ?? "NONE")}
      </Badge>
      <Badge>Finance: {words(job.financial_state ?? "PREPAID")}</Badge>
    </div>
  );
}

export function JobMatrix({
  order,
  selectedJobId,
  onSelect,
}: {
  order: OrderView;
  selectedJobId?: string;
  onSelect: (id: string) => void;
}) {
  const [filter, setFilter] = useState<Tone | "all">("all");
  const [search, setSearch] = useState("");
  const progress = originalProgress(order);
  const filtered = progress.jobs.filter(
    (j) =>
      (filter === "all" || jobTone(j) === filter) &&
      `${j.label} ${j.id}`.toLowerCase().includes(search.toLowerCase()),
  );
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  return (
    <section className="panel matrix-panel" aria-label="Original job matrix">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Original delivery</span>
          <h2>Every job, accounted for.</h2>
        </div>
        <Badge>{progress.total} original units</Badge>
      </div>
      <div className="progress-copy">
        <strong>
          {progress.accepted} / {progress.total} accepted
        </strong>
        <span>{progress.validated} validated</span>
      </div>
      <progress
        max={progress.total}
        value={progress.accepted}
        aria-label="Original units accepted"
      />
      <div className="filters" aria-label="Filter jobs">
        <Button
          variant="ghost"
          aria-pressed={filter === "all"}
          onClick={() => setFilter("all")}
        >
          All {progress.jobs.length}
        </Button>
        {(["green", "red", "orange", "blue"] as Tone[]).map((tone) => (
          <Button
            key={tone}
            variant="ghost"
            aria-pressed={filter === tone}
            onClick={() => setFilter(tone)}
          >
            <span className={`dot ${tone}`} />
            {toneLabels[tone]} {progress.counts[tone]}
          </Button>
        ))}
      </div>
      <label className="search">
        <span className="sr-only">Find a job</span>
        <input
          type="search"
          placeholder="Find a job…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span>
          {filtered.length} shown / {progress.total} original
        </span>
      </label>
      <div className="job-grid" aria-label="Jobs; use arrow keys to move">
        {filtered.map((job, index) => (
          <button
            ref={(element) => {
              if (element) buttons.current.set(job.id, element);
              else buttons.current.delete(job.id);
            }}
            type="button"
            key={job.id}
            className={`job-tile ${jobTone(job)} ${selectedJobId === job.id ? "selected" : ""}`}
            aria-pressed={selectedJobId === job.id}
            aria-label={`${job.label}. Processing ${job.processing}; dispute ${job.dispute ?? "NONE"}; finance ${job.financial_state ?? "PREPAID"}`}
            title={`${job.label} · ${job.processing} · ${job.dispute ?? "NONE"} · ${job.financial_state ?? "PREPAID"}`}
            onKeyDown={(e) => {
              const count = e.currentTarget.parentElement
                ? getComputedStyle(
                    e.currentTarget.parentElement,
                  ).gridTemplateColumns.split(" ").length
                : 10;
              const offset = (
                {
                  ArrowRight: 1,
                  ArrowLeft: -1,
                  ArrowDown: count,
                  ArrowUp: -count,
                } as Record<string, number>
              )[e.key];
              if (offset !== undefined) {
                e.preventDefault();
                const next =
                  filtered[
                    Math.max(0, Math.min(filtered.length - 1, index + offset))
                  ];
                if (next) buttons.current.get(next.id)?.focus();
              }
            }}
            onClick={() => onSelect(job.id)}
          >
            <span>
              {String(job.original_index ?? index + 1).padStart(2, "0")}
            </span>
            <small aria-hidden="true">
              {activeDispute(job)
                ? "?"
                : job.processing === "VALIDATED"
                  ? "✓"
                  : job.processing === "FAILED"
                    ? "!"
                    : "·"}
            </small>
            {activeDispute(job) && job.processing === "FAILED" && (
              <span className="failure-dot" aria-label="Also failed" />
            )}
          </button>
        ))}
      </div>
      {!filtered.length && (
        <p className="empty-inline">No jobs match this filter.</p>
      )}
      <p className="small muted matrix-note">
        Disputes take orange precedence; a red dot preserves a simultaneous
        failure. Correction attempts and added scope never inflate the original
        denominator.
      </p>
    </section>
  );
}

export function Workbench() {
  const app = useWorkbench();
  const { order, session } = app;
  const busy = app.busy || !!app.failed;
  const [jobId, setJobId] = useState<string>();
  const [checkId, setCheckId] = useState<string>();
  const [issueId, setIssueId] = useState<string>();
  const [autoFollow, setAutoFollow] = useState(false);
  const [traversal, setTraversal] = useState<string[]>();
  const [visited, setVisited] = useState<string[]>([]);
  const [walkNotice, setWalkNotice] = useState("");
  const [disputeText, setDisputeText] = useState("");
  const lastEvent = useRef<string | undefined>(undefined);
  const focusJob = (id: string) => {
    setJobId(id);
    setCheckId(undefined);
    setIssueId(undefined);
    setDisputeText("");
  };
  useEffect(() => {
    setJobId(undefined);
    setCheckId(undefined);
    setIssueId(undefined);
    setTraversal(undefined);
    setVisited([]);
    setWalkNotice("");
    setAutoFollow(false);
    lastEvent.current = undefined;
  }, [app.selectedId, session?.actor.id]);
  useEffect(() => {
    const newest = app.events.at(-1);
    if (newest?.id === lastEvent.current) return;
    const previous = lastEvent.current;
    lastEvent.current = newest?.id;
    if (
      autoFollow &&
      previous &&
      newest?.job_id &&
      order?.jobs.some((j) => j.id === newest.job_id)
    )
      focusJob(newest.job_id);
  }, [app.events, autoFollow, order]);

  const command = async (input: CommandInput, label: string) => {
    if (!order) return false;
    return app.mutate(
      prepareMutation(
        `/orders/${encodeURIComponent(order.id)}/commands`,
        input,
        label,
        order.revision,
      ),
    );
  };
  const createOrder = () =>
    void app.mutate(
      prepareMutation(
        "/orders",
        {
          customer_name: "Northwind",
          title: "Document extraction · Northwind",
          document_count: 100,
          failed_count: 20,
        },
        "Fresh Northwind case",
      ),
    );
  const job = order?.jobs.find((j) => j.id === jobId);
  const check = job?.checks?.find((c) => c.id === checkId);
  const issue = order?.issues?.find((i) => i.id === issueId);
  const relatedIssues =
    order?.issues?.filter(
      (i) =>
        job &&
        ((job.issue_ids ?? []).includes(i.id) || i.job_ids.includes(job.id)),
    ) ?? [];
  const openIssues =
    order?.issues?.filter(
      (i) => i.state !== "RESOLVED" && i.state !== "NONE",
    ) ?? [];
  const correctable = order ? recoverableJobs(order) : [];
  const acceptable = order ? acceptableJobs(order) : [];
  const next = () => {
    if (!order) return;
    const ids = traversal ?? unresolvedIds(order);
    setTraversal(ids);
    const id = nextInTraversal(ids, visited, order);
    if (!id) {
      setWalkNotice(
        "End of this review pass. Waiting issues remain visible; no work was started.",
      );
      return;
    }
    setVisited((old) => [...old, id]);
    focusJob(id);
    const target = order.jobs.find((j) => j.id === id);
    setWalkNotice(
      target?.dispute?.startsWith("WAITING")
        ? "Waiting for a targeted response. Review paused; use Next unresolved when ready."
        : `Reviewing ${visited.length + 1} of ${ids.length} in this bounded pass.`,
    );
  };
  const pausePresentation = (target: EventTarget) => {
    if (
      target instanceof Element &&
      target.closest("[data-presentation-control]")
    )
      return;
    setAutoFollow(false);
  };
  return (
    <div
      className="app-shell"
      onPointerDownCapture={(e) => pausePresentation(e.target)}
      onFocusCapture={(e) => pausePresentation(e.target)}
      onKeyDownCapture={(e) => pausePresentation(e.target)}
      onInputCapture={(e) => pausePresentation(e.target)}
    >
      <a className="skip-link" href="#main">
        Skip to workbench
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="OBJECTION home">
          <span className="brand-mark">
            o<span />
          </span>
          OBJECTION<span className="brand-period">.</span>
        </a>
        <p className="sidebar-kicker">ORDER OPERATIONS</p>
        <div className="nav-active">
          <span>▦</span> Job workbench
        </div>
        <div className="sidebar-heading">
          <h2>Order requests</h2>
          <Badge>{app.orders.length}</Badge>
        </div>
        <nav aria-label="Order requests" className="orders-list">
          {app.orders.map((item) => (
            <button
              key={item.id}
              disabled={busy}
              className={`order-link ${app.selectedId === item.id ? "active" : ""}`}
              aria-current={app.selectedId === item.id ? "page" : undefined}
              onClick={() => app.selectOrder(item.id)}
            >
              <span className="customer-avatar">
                {item.customer_name.slice(0, 1)}
              </span>
              <span>
                <strong>{item.customer_name}</strong>
                <small>{item.title}</small>
                <small>{words(item.status ?? "ACTIVE")}</small>
              </span>
            </button>
          ))}
        </nav>
        <Button
          className="new-case"
          disabled={!session || busy}
          onClick={createOrder}
        >
          ＋ New Northwind case
        </Button>
        <div className="sidebar-footer">
          <span className="live-dot" />
          <strong>Local demonstration</strong>
          <p>
            Synthetic evidence.
            <br />
            Simulated money & provider.
          </p>
        </div>
      </aside>
      <main id="main" className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">Operations / Workbench</span>
            <h1>From delivery to resolution.</h1>
          </div>
          <label className="identity">
            Local demo identity
            <select
              value={session?.actor.id ?? ""}
              disabled={busy}
              onChange={(e) => void app.switchSession(e.target.value)}
            >
              <option value="" disabled>
                Select a registered identity
              </option>
              {app.actors.map((actor) => (
                <option key={actor.id} value={actor.id}>
                  {actor.name} · {actor.role}
                </option>
              ))}
            </select>
          </label>
        </header>
        <div className="disclosure">
          <span>LOCAL DEMO</span> Synthetic evidence · simulated money and
          provider execution · no real settlement
        </div>
        {(app.error || app.notice || app.failed) && (
          <div
            className={`notice ${app.error || app.failed ? "error" : ""}`}
            role={app.error || app.failed ? "alert" : "status"}
          >
            <div>
              {app.error ??
                app.notice ??
                "The previous request has an uncertain outcome."}
              {app.failed && (
                <p>
                  New mutations and identity changes are paused. Retry uses the
                  original key, payload and revision.
                </p>
              )}
            </div>
            <div className="row">
              {app.failed && (
                <Button
                  disabled={app.busy}
                  onClick={() => void app.mutate(app.failed!)}
                >
                  Retry exact request
                </Button>
              )}
              <Button disabled={app.busy} onClick={app.refresh}>
                Refresh
              </Button>
              <Button variant="ghost" onClick={app.dismiss}>
                Dismiss
              </Button>
            </div>
          </div>
        )}
        {!session && (
          <section className="welcome panel">
            <span className="eyebrow">An evidence-led workbench</span>
            <h2>One batch. Every obligation in view.</h2>
            <p>
              Choose a registered local demo identity to open authorized order
              requests. Identity comes from the backend; a browser role is never
              authorization.
            </p>
            {!app.actors.length && (
              <Button onClick={app.refresh}>Retry connection</Button>
            )}
          </section>
        )}
        {session && !order && (
          <section className="welcome panel" aria-busy={app.loading}>
            <h2>
              {app.loading
                ? "Loading authorized orders…"
                : "Start with a fresh case."}
            </h2>
            <p>
              Create Northwind’s synthetic 100-document batch. All jobs,
              evidence, events and money balances will be created by the
              backend.
            </p>
            <Button
              disabled={busy || app.loading}
              variant="primary"
              onClick={createOrder}
            >
              Create Northwind case
            </Button>
          </section>
        )}
        {order && session && (
          <>
            <div className="order-heading">
              <div>
                <span className="eyebrow">
                  {order.customer_name} / {order.id}
                </span>
                <h2>{order.title}</h2>
              </div>
              <div className="row">
                <Badge>{words(order.status ?? "ACTIVE")}</Badge>
                <span className="small muted">
                  revision {order.revision}
                  {app.loading ? " · syncing" : " · live snapshot"}
                </span>
                <FinanceDrawer
                  order={order}
                  events={app.events}
                  actor={session.actor}
                  busy={busy}
                  command={command}
                />
              </div>
            </div>
            <section
              className="money-cards"
              aria-label="Authoritative financial summary"
            >
              {[
                {
                  title: "Cash received",
                  value: order.finance?.received_minor,
                  note: "Confirmed simulated receipts",
                  icon: "↙",
                },
                {
                  title: "Earned revenue",
                  value: order.finance?.recognized_minor,
                  note: "Accepted delivery only",
                  icon: "✓",
                },
                {
                  title: "Contract liability",
                  value: order.finance?.liability_minor,
                  note: "Prepaid work still owed",
                  icon: "◷",
                },
                {
                  title: "Correction cost",
                  value: order.finance?.correction_cost_minor,
                  note: "Internal cost · no extra debit",
                  icon: "↻",
                },
              ].map((card) => (
                <article className="money-card" key={card.title}>
                  <div className="row spread">
                    <span>{card.title}</span>
                    <span aria-hidden="true" className="money-icon">
                      {card.icon}
                    </span>
                  </div>
                  <strong>{money(card.value)}</strong>
                  <small>{card.note}</small>
                </article>
              ))}
            </section>
            {!!order.finance?.unknown_minor && (
              <p className="notice warning">
                {money(order.finance.unknown_minor)} payment UNKNOWN — excluded
                from cash. Reconcile the existing operation in Finance receipts.
              </p>
            )}
            <div className="workspace-toolbar">
              <nav aria-label="Breadcrumb" className="breadcrumbs">
                <button
                  onClick={() => {
                    setJobId(undefined);
                    setCheckId(undefined);
                    setIssueId(undefined);
                  }}
                >
                  Overview
                </button>
                {job && (
                  <>
                    <span>/</span>
                    <button
                      onClick={() => {
                        setCheckId(undefined);
                        setIssueId(undefined);
                      }}
                    >
                      {job.label}
                    </button>
                  </>
                )}
                {check && (
                  <>
                    <span>/</span>
                    <button onClick={() => setIssueId(undefined)}>
                      {check.label}
                    </button>
                  </>
                )}
                {issue && (
                  <>
                    <span>/</span>
                    <strong>{issue.title}</strong>
                  </>
                )}
              </nav>
              <div className="row">
                <Button onClick={next}>Next unresolved →</Button>
                {walkNotice.startsWith("End") && (
                  <Button
                    onClick={() => {
                      setTraversal(undefined);
                      setVisited([]);
                      setWalkNotice("");
                    }}
                  >
                    New review pass
                  </Button>
                )}
                <label
                  className="presentation-control"
                  data-presentation-control
                >
                  <input
                    type="checkbox"
                    checked={autoFollow}
                    onChange={(e) => setAutoFollow(e.target.checked)}
                  />
                  Presentation auto-follow
                </label>
              </div>
            </div>
            {walkNotice && (
              <p className="small muted" role="status">
                {walkNotice}
              </p>
            )}
            <div className="work-area">
              <div className="batch-column">
                <JobMatrix
                  key={order.id}
                  order={order}
                  selectedJobId={jobId}
                  onSelect={focusJob}
                />
                <div className="batch-actions">
                  <div>
                    <strong>Original delivery actions</strong>
                    <p className="small muted">
                      Corrections do not imply customer acceptance.
                    </p>
                  </div>
                  <div className="row">
                    {can(session.actor, "correct") && (
                      <Button
                        variant="primary"
                        disabled={busy || !correctable.length}
                        onClick={() =>
                          void command(
                            {
                              verb: "correct",
                              job_ids: correctable.map((j) => j.id),
                            },
                            "Bounded correction",
                          )
                        }
                      >
                        Correct {correctable.length} failed jobs
                      </Button>
                    )}
                    {can(session.actor, "accept_delivery") && (
                      <Button
                        variant="primary"
                        disabled={busy || !acceptable.length}
                        onClick={() =>
                          void command(
                            {
                              verb: "accept_delivery",
                              job_ids: acceptable.map((j) => j.id),
                            },
                            "Accept validated originals",
                          )
                        }
                      >
                        Accept {acceptable.length} validated originals
                      </Button>
                    )}
                    <EvidenceDrawer order={order} token={session.token} />
                  </div>
                </div>
                <Courier
                  key={order.id}
                  events={app.events}
                  jobs={order.jobs}
                  attemptLimit={order.agreement.correction_attempt_limit ?? 1}
                />
                <ChangeOrders
                  order={order}
                  actor={session.actor}
                  token={session.token}
                  busy={busy}
                  command={command}
                />
                {order.jobs.some((j) => j.kind && j.kind !== "ORIGINAL") && (
                  <details className="panel">
                    <summary>
                      Related work · outside original denominator
                    </summary>
                    {order.jobs
                      .filter((j) => j.kind && j.kind !== "ORIGINAL")
                      .map((child) => (
                        <Button
                          key={child.id}
                          onClick={() => focusJob(child.id)}
                        >
                          {child.label} · {words(child.kind)} ·{" "}
                          {words(child.processing)}
                        </Button>
                      ))}
                  </details>
                )}
              </div>
              <div className="detail-column">
                {issue ? (
                  <div className="panel">
                    <Button
                      variant="ghost"
                      onClick={() => setIssueId(undefined)}
                    >
                      ← Back to {job ? "job" : "overview"}
                    </Button>
                    <IssuePanel
                      key={`${order.id}:${issue.id}:${session.actor.id}`}
                      order={order}
                      issue={issue}
                      actor={session.actor}
                      token={session.token}
                      busy={busy}
                      command={command}
                      mutate={app.mutate}
                    />
                  </div>
                ) : job ? (
                  <section
                    className="panel job-detail"
                    aria-label={`Job details: ${job.label}`}
                  >
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">Job inspection</span>
                        <h2>{job.label}</h2>
                      </div>
                      <Button
                        variant="ghost"
                        aria-label="Close job details"
                        onClick={() => {
                          setJobId(undefined);
                          setCheckId(undefined);
                        }}
                      >
                        ✕
                      </Button>
                    </div>
                    <Axes job={job} />
                    <p className="small muted">
                      Owner: {job.owner ?? "provider"} · obligation:{" "}
                      {words(job.obligation ?? "OPEN")}
                    </p>
                    <div className="next-action">
                      <strong>Next action</strong>
                      <p>{job.next_action}</p>
                    </div>
                    <div className="pipeline">
                      <span>Source</span>
                      <span>→ Extract</span>
                      <span>→ Validate</span>
                      <span>→ Accept</span>
                    </div>
                    <h3>Checks</h3>
                    <div className="check-list">
                      {job.checks?.map((item) => (
                        <button
                          key={item.id}
                          aria-pressed={checkId === item.id}
                          onClick={() => setCheckId(item.id)}
                        >
                          <span>{item.label}</span>
                          <Badge
                            tone={
                              item.state === "FAILED"
                                ? "red"
                                : item.state === "PASSED"
                                  ? "green"
                                  : item.state === "DISPUTED"
                                    ? "orange"
                                    : "blue"
                            }
                          >
                            {words(item.state)}
                          </Badge>
                        </button>
                      ))}
                    </div>
                    {check && (
                      <section className="check-detail">
                        <h3>{check.label}</h3>
                        <p>{check.detail}</p>
                        <CitationList
                          order={order}
                          citations={check.citations ?? []}
                          token={session.token}
                        />
                      </section>
                    )}
                    {relatedIssues.length > 0 && (
                      <>
                        <h3>Related issue conversations</h3>
                        {relatedIssues.map((item) => (
                          <button
                            className="issue-link"
                            key={item.id}
                            onClick={() => setIssueId(item.id)}
                          >
                            <strong>{item.title}</strong>
                            <span>
                              {words(item.state ?? "OPEN")} · {item.owner} →
                            </span>
                          </button>
                        ))}
                      </>
                    )}
                    <details>
                      <summary>Source document</summary>
                      <SourceCard
                        order={order}
                        sourceId={job.source_id}
                        token={session.token}
                      />
                    </details>
                    {job.artifact_id && (
                      <details>
                        <summary>
                          Current delivery{" "}
                          {job.accepted_artifact_id === job.artifact_id
                            ? "· accepted"
                            : "· not accepted"}
                        </summary>
                        <SourceCard
                          order={order}
                          sourceId={job.artifact_id}
                          token={session.token}
                        />
                      </details>
                    )}
                    {!!job.attempts?.length && (
                      <details open>
                        <summary>Persisted correction attempts</summary>
                        {job.attempts.map((attempt) => (
                          <article className="inset" key={attempt.id}>
                            <Badge
                              tone={
                                attempt.status === "FAILED"
                                  ? "red"
                                  : attempt.status === "UNKNOWN"
                                    ? "orange"
                                    : "blue"
                              }
                            >
                              {attempt.status}
                            </Badge>
                            <p className="small wrap">
                              Attempt {attempt.number}: {attempt.id}
                              <br />
                              Operation: {attempt.operation_id}
                              <br />
                              Retry from:{" "}
                              {attempt.retry_from_stage ?? "extract"} · cost{" "}
                              {money(attempt.cost_minor)}
                            </p>
                            {attempt.error && (
                              <p className="error-text">{attempt.error}</p>
                            )}
                            {attempt.output_artifact_id && (
                              <details>
                                <summary>Inspect attempt output</summary>
                                <SourceCard
                                  order={order}
                                  sourceId={attempt.output_artifact_id}
                                  token={session.token}
                                />
                              </details>
                            )}
                            {attempt.status === "UNKNOWN" &&
                              can(session.actor, "reconcile") && (
                                <Button
                                  disabled={busy}
                                  onClick={() =>
                                    void command(
                                      {
                                        verb: "reconcile",
                                        operation_id: attempt.operation_id,
                                        job_ids: [job.id],
                                      },
                                      "Reconcile correction intent",
                                    )
                                  }
                                >
                                  Reconcile UNKNOWN attempt
                                </Button>
                              )}
                          </article>
                        ))}
                      </details>
                    )}
                    <div className="row">
                      {can(session.actor, "correct") &&
                        correctable.some((j) => j.id === job.id) && (
                          <Button
                            variant="primary"
                            disabled={busy}
                            onClick={() =>
                              void command(
                                { verb: "correct", job_ids: [job.id] },
                                "Correct selected job",
                              )
                            }
                          >
                            Correct this job
                          </Button>
                        )}
                      {can(session.actor, "accept_delivery") &&
                        acceptable.some((j) => j.id === job.id) && (
                          <Button
                            disabled={busy}
                            onClick={() =>
                              void command(
                                { verb: "accept_delivery", job_ids: [job.id] },
                                "Accept selected delivery",
                              )
                            }
                          >
                            Accept this delivery
                          </Button>
                        )}
                    </div>
                    {can(session.actor, "open_dispute") && (
                      <details>
                        <summary>Open a customer dispute</summary>
                        <form
                          className="form-stack"
                          onSubmit={(e) => {
                            e.preventDefault();
                            void command(
                              {
                                verb: "open_dispute",
                                job_ids: [job.id],
                                text: disputeText,
                              },
                              "Open dispute",
                            );
                          }}
                        >
                          <label>
                            What needs review?
                            <textarea
                              required
                              value={disputeText}
                              onChange={(e) => setDisputeText(e.target.value)}
                              maxLength={12000}
                            />
                          </label>
                          <Button
                            type="submit"
                            disabled={busy || !disputeText.trim()}
                          >
                            Open dispute
                          </Button>
                        </form>
                      </details>
                    )}
                  </section>
                ) : (
                  <section className="panel attention">
                    <span className="eyebrow">Exception inbox</span>
                    <h2>Focus where it matters.</h2>
                    <p className="muted">
                      Select a job to inspect its checks, exact evidence and
                      delivery history. Open an issue to review only its
                      conversation.
                    </p>
                    <div className="attention-count">
                      <strong>{openIssues.length}</strong>
                      <span>
                        open issues
                        <br />
                        <small>Each with an owner & next action</small>
                      </span>
                    </div>
                    {openIssues.map((item) => (
                      <button
                        className="issue-link"
                        key={item.id}
                        onClick={() => setIssueId(item.id)}
                      >
                        <div className="row spread">
                          <strong>{item.title}</strong>
                          <span>↗</span>
                        </div>
                        <Badge tone="orange">
                          {words(item.state ?? "OPEN")}
                        </Badge>
                        <span>
                          Owner: {item.owner ?? "investigator"}
                          <br />
                          Next: {item.next_action}
                        </span>
                      </button>
                    ))}
                    {!openIssues.length && (
                      <p className="muted">
                        No open issue is recorded. Delivery and finance may
                        still have outstanding obligations.
                      </p>
                    )}
                    <div className="reading-note">
                      <span>↗</span>
                      <p>
                        <strong>You control the focus.</strong>
                        <br />
                        Reading, typing and clicking pause presentation
                        auto-follow. New results never authorize actions.
                      </p>
                    </div>
                  </section>
                )}
              </div>
            </div>
            <footer className="footer">
              <span>OBJECTION / evidence before action</span>
              <span>
                {order.agreement.policy_id ?? "saas-unit-acceptance-v1"} ·{" "}
                {order.finance?.currency ?? "USD_SIM"} · 2 decimals
              </span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
