"use client";
import { useState } from "react";
import type {
  Actor,
  DocumentUpload,
  Issue,
  OrderView,
  Question,
} from "../lib/jobflow.generated";
import {
  encodeUpload,
  prepareMutation,
  type CommandInput,
  type PreparedMutation,
} from "../lib/api";
import { can, historical, money, words } from "../lib/projection";
import { CitationList, SourceCard } from "./evidence";
import { Badge, Button, Drawer } from "./ui";

type Props = {
  order: OrderView;
  issue: Issue;
  actor: Actor;
  token: string;
  busy: boolean;
  command: (input: CommandInput, label: string) => Promise<boolean>;
  mutate: (mutation: PreparedMutation) => Promise<boolean>;
};
function AnswerForm({
  question,
  busy,
  command,
}: {
  question: Question;
  busy: boolean;
  command: Props["command"];
}) {
  const [answer, setAnswer] = useState("");
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        if (
          await command(
            {
              verb: "answer",
              issue_id: question.issue_id,
              question_id: question.id,
              text: answer.trim(),
            },
            "Targeted answer",
          )
        )
          setAnswer("");
      }}
      className="answer-form"
    >
      <label htmlFor={`answer-${question.id}`}>Answer this question</label>
      <textarea
        id={`answer-${question.id}`}
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        required
        maxLength={12000}
        placeholder="Provide the requested evidence or explain what is unknown…"
      />
      <div className="row spread">
        <span className="muted small">
          Saved as a party assertion, not authorization.
        </span>
        <Button
          type="submit"
          variant="primary"
          disabled={busy || !answer.trim()}
        >
          Send answer ↗
        </Button>
      </div>
    </form>
  );
}

function IssueEvidence({
  order,
  issue,
  actor,
  token,
  busy,
  command,
  mutate,
}: Props) {
  const [fields, setFields] = useState(issue.field);
  const [effectiveAt, setEffectiveAt] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string>();
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File>();
  const [kind, setKind] = useState<DocumentUpload["kind"]>("message");
  const signing = can(actor, "amend_agreement");
  return (
    <Drawer
      title="Issue evidence & agreement"
      description={`${issue.title} · ${issue.id}. Separate customer and provider signatures are required.`}
      wide
      trigger={<Button>Evidence & amendments ↗</Button>}
    >
      <h3>Accepted agreement · v{order.agreement.version ?? 1}</h3>
      <p>{order.agreement.fields.join(", ")}</p>
      <SourceCard
        order={order}
        sourceId={order.agreement.source_id}
        token={token}
      />
      <h3>Amendments</h3>
      {order.agreement.amendments?.map((amendment) => (
        <article key={amendment.id} className="inset">
          <strong>{amendment.fields.join(", ")}</strong>
          <p className="small">
            {amendment.id} · effective {amendment.effective_at}
          </p>
          <p className="small">
            Customer signature: {amendment.accepted_by_customer ?? "Missing"}
            <br />
            Provider signature: {amendment.accepted_by_provider ?? "Missing"}
          </p>
          <SourceCard
            order={order}
            sourceId={amendment.source_id}
            token={token}
          />
          {signing &&
            !(actor.role === "customer"
              ? amendment.accepted_by_customer
              : amendment.accepted_by_provider) && (
              <Button
                disabled={busy}
                onClick={() =>
                  void command(
                    {
                      verb: "amend_agreement",
                      amendment_id: amendment.id,
                      issue_id: issue.id,
                      fields: amendment.fields,
                      effective_at: amendment.effective_at,
                    },
                    `Sign amendment as ${actor.role}`,
                  )
                }
              >
                Sign as {actor.role}
              </Button>
            )}
        </article>
      ))}
      {signing && (
        <form
          className="inset form-stack"
          onSubmit={async (event) => {
            event.preventDefault();
            await command(
              {
                verb: "amend_agreement",
                issue_id: issue.id,
                fields: fields
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
                effective_at: new Date(effectiveAt).toISOString(),
                text: text.trim(),
              },
              `Propose amendment with ${actor.role} signature`,
            );
          }}
        >
          <h4>Propose & sign amendment as {actor.role}</h4>
          <p className="small muted">
            The other party must sign independently. Effective time is evaluated
            by the backend.
          </p>
          <label>
            Fields (comma-separated)
            <input
              required
              value={fields}
              onChange={(e) => setFields(e.target.value)}
            />
          </label>
          <label>
            Effective time (your local time)
            <input
              required
              type="datetime-local"
              value={effectiveAt}
              onChange={(e) => setEffectiveAt(e.target.value)}
            />
          </label>
          <label>
            Agreement text
            <textarea
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={12000}
            />
          </label>
          <Button
            type="submit"
            disabled={busy || !fields.trim() || !text.trim()}
            variant="primary"
          >
            Record my signature
          </Button>
        </form>
      )}
      <h3>Upload supporting evidence</h3>
      <p className="muted small">
        PDF, text, JSON or CSV · maximum 2 MiB. Uploaded content remains an
        unverified party assertion.
      </p>
      <form
        className="form-stack"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!file) return;
          setError(undefined);
          setUploading(true);
          try {
            const types: Record<string, DocumentUpload["media_type"]> = {
              pdf: "application/pdf",
              txt: "text/plain",
              json: "application/json",
              csv: "text/csv",
            };
            const mediaType =
              types[file.name.split(".").at(-1)?.toLowerCase() ?? ""];
            if (!mediaType)
              throw new Error("Choose a PDF, TXT, JSON or CSV file.");
            const content = await encodeUpload(file);
            await mutate(
              prepareMutation(
                `/orders/${encodeURIComponent(order.id)}/documents`,
                {
                  filename: file.name,
                  media_type: mediaType,
                  content_base64: content,
                  kind,
                  issue_id: issue.id,
                },
                "Evidence upload",
                order.revision,
              ),
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setUploading(false);
          }
        }}
      >
        <label>
          Document
          <input
            type="file"
            accept=".pdf,.txt,.json,.csv"
            onChange={(e) => setFile(e.target.files?.[0])}
            required
          />
        </label>
        <label>
          Evidence kind
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as DocumentUpload["kind"])}
          >
            <option value="message">Message</option>
            <option value="amendment">Amendment assertion</option>
            <option value="agreement">Agreement assertion</option>
            <option value="source">Source</option>
          </select>
        </label>
        <Button type="submit" disabled={busy || uploading || !file}>
          {uploading ? "Preparing upload…" : "Upload unverified assertion"}
        </Button>
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
      </form>
    </Drawer>
  );
}

export function IssuePanel(props: Props) {
  const { order, issue, actor, token, busy, command, mutate } = props;
  const [mode, setMode] = useState<"DETERMINISTIC" | "ANTHROPIC">(
    "DETERMINISTIC",
  );
  const [handoff, setHandoff] = useState("");
  const actions = (order.actions ?? []).filter((a) => a.issue_id === issue.id);
  const runs = (order.investigations ?? []).filter(
    (r) => r.issue_id === issue.id,
  );
  const running = runs.some(
    (r) => r.status === "QUEUED" || r.status === "RUNNING",
  );
  return (
    <section className="issue-panel" aria-label={`Issue: ${issue.title}`}>
      <header className="section-heading">
        <div>
          <span className="eyebrow">Issue conversation</span>
          <h2>{issue.title}</h2>
        </div>
        <Badge tone={issue.state === "RESOLVED" ? "green" : "orange"}>
          {words(issue.state ?? "OPEN")}
        </Badge>
      </header>
      <p className="muted small">
        {issue.id} · owner: {issue.owner ?? "investigator"}
      </p>
      <div className="next-action">
        <strong>Next action</strong>
        <p>{issue.next_action}</p>
      </div>
      <div className="row">
        <IssueEvidence {...props} />
        {actor.role === "investigator" && (
          <>
            <label className="inline-label">
              Investigation mode
              <select
                value={mode}
                disabled={busy || running}
                onChange={(e) => setMode(e.target.value as typeof mode)}
              >
                <option value="DETERMINISTIC">
                  Deterministic · scripted analysis
                </option>
                <option value="ANTHROPIC" disabled={!order.model_available}>
                  Anthropic ·{" "}
                  {order.model_available ? "configured model" : "unavailable"}
                </option>
              </select>
            </label>
            <Button
              variant="primary"
              disabled={busy || running || issue.state === "RESOLVED"}
              onClick={() =>
                void mutate(
                  prepareMutation(
                    `/orders/${encodeURIComponent(order.id)}/investigations`,
                    { issue_id: issue.id, mode },
                    "Investigation",
                    order.revision,
                  ),
                )
              }
            >
              {running ? "Investigation in progress…" : "Investigate issue"}
            </Button>
          </>
        )}
      </div>
      {!order.model_available && (
        <p className="muted small">
          Optional model access is unavailable. Deterministic investigation
          remains available to the investigator identity.
        </p>
      )}
      {runs.map((run) => (
        <p className="small wrap" key={run.id}>
          <Badge
            tone={
              run.status === "FAILED" || run.status === "BLOCKED"
                ? "orange"
                : "neutral"
            }
          >
            {run.mode} · {run.status}
          </Badge>{" "}
          {run.elapsed_ms != null && `${run.elapsed_ms} ms`} {run.error}
        </p>
      ))}
      <div className="conversation" aria-label="Selected issue messages">
        {(issue.messages ?? [])
          .filter((m) => m.issue_id === issue.id)
          .map((message) => (
            <article
              className={`message ${message.author_id === actor.id ? "mine" : ""}`}
              key={message.id}
            >
              <div className="row spread">
                <strong>{message.author_name}</strong>
                <time className="small muted" dateTime={message.timestamp}>
                  {new Date(message.timestamp).toLocaleString()}
                </time>
              </div>
              <p>{message.text}</p>
              {message.question_id && (
                <span className="small muted">
                  Reply to {message.question_id}
                </span>
              )}
              {message.source_id && (
                <details>
                  <summary>Inspect message source</summary>
                  <SourceCard
                    order={order}
                    sourceId={message.source_id}
                    token={token}
                  />
                </details>
              )}
            </article>
          ))}
        {!issue.messages?.length && (
          <p className="muted">No messages recorded for this issue.</p>
        )}
      </div>
      {(issue.questions ?? [])
        .filter((q) => q.issue_id === issue.id)
        .map((question) => (
          <article className="question-card" key={question.id}>
            <div className="row spread">
              <span className="eyebrow">Question for {question.recipient}</span>
              <Badge tone={question.status === "ANSWERED" ? "green" : "orange"}>
                {question.status ?? "OPEN"}
              </Badge>
            </div>
            <h3>{question.text}</h3>
            <p className="small muted">
              Question {question.id} · issue {question.issue_id}
            </p>
            {(question.status ?? "OPEN") === "OPEN" &&
            actor.role === question.recipient ? (
              <AnswerForm question={question} busy={busy} command={command} />
            ) : (
              (question.status ?? "OPEN") === "OPEN" && (
                <p className="small muted">
                  Switch Local demo identity to a registered{" "}
                  {question.recipient} to answer this exact question.
                </p>
              )
            )}
          </article>
        ))}
      {(issue.findings ?? []).map((finding) => (
        <article className="finding" key={finding.id}>
          <Badge>{finding.status}</Badge>
          <p>{finding.statement}</p>
          <CitationList
            order={order}
            citations={finding.citations ?? []}
            token={token}
          />
        </article>
      ))}
      {actions.length > 0 && <h3>Recommendations & decisions</h3>}
      {actions.map((action) => {
        const old = historical(action, order);
        const approval = order.approvals?.find(
          (a) =>
            a.action_id === action.id &&
            a.actor_id !== actor.id &&
            Date.parse(a.expires_at) > Date.now(),
        );
        return (
          <article
            key={action.id}
            className={`inset ${old ? "historical" : ""}`}
          >
            <div className="row spread">
              <strong>
                {words(action.kind)} · {money(action.amount_minor)}
              </strong>
              <Badge>
                {old
                  ? `Historical · ${action.status ?? "PROPOSED"}`
                  : (action.status ?? "PROPOSED")}
              </Badge>
            </div>
            <p>{action.basis}</p>
            <p className="small muted wrap">
              {action.id} · proposal revision {action.revision} · agreement v
              {action.agreement_version}
              <br />
              Expires {action.expires_at} · owner {action.owner}
            </p>
            <p className="small">
              Fields: {action.fields?.join(", ") || "None"} · affected jobs:{" "}
              {action.job_ids?.length ?? 0}
            </p>
            <details>
              <summary>Cited basis & version binding</summary>
              <p className="small wrap">
                Evidence digest: {action.evidence_digest}
                <br />
                Scope digest: {action.scope_digest}
              </p>
              <CitationList
                order={order}
                citations={action.citations ?? []}
                token={token}
              />
            </details>
            {!old && (
              <div className="row">
                {(action.status ?? "PROPOSED") === "PROPOSED" &&
                  can(actor, "approve_action") && (
                    <>
                      <Button
                        disabled={busy}
                        variant="primary"
                        onClick={() =>
                          void command(
                            {
                              verb: "approve_action",
                              action_id: action.id,
                              issue_id: issue.id,
                            },
                            "Approve exception",
                          )
                        }
                      >
                        Approve exception
                      </Button>
                      <Button
                        disabled={busy}
                        onClick={() =>
                          void command(
                            {
                              verb: "decline_action",
                              action_id: action.id,
                              issue_id: issue.id,
                            },
                            "Decline exception",
                          )
                        }
                      >
                        Decline
                      </Button>
                    </>
                  )}
                {action.status === "APPROVED" &&
                  can(actor, "execute_action") && (
                    <Button
                      disabled={busy || !approval}
                      variant="primary"
                      onClick={() =>
                        void command(
                          {
                            verb: "execute_action",
                            action_id: action.id,
                            approval_id: approval?.id,
                            issue_id: issue.id,
                          },
                          "Execute approved action",
                        )
                      }
                    >
                      Execute approved action
                    </Button>
                  )}
              </div>
            )}
          </article>
        );
      })}
      {issue.resolution && (
        <div className="notice">
          <strong>Recorded resolution</strong>
          <p>{issue.resolution}</p>
        </div>
      )}
      {can(actor, "handoff") && issue.state !== "RESOLVED" && (
        <details>
          <summary>Hand off for human review</summary>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              void command(
                { verb: "handoff", issue_id: issue.id, text: handoff },
                "Human-review handoff",
              );
            }}
          >
            <label>
              Owner, reason and next action
              <textarea
                required
                value={handoff}
                onChange={(e) => setHandoff(e.target.value)}
              />
            </label>
            <Button type="submit" disabled={busy || !handoff.trim()}>
              Record handoff
            </Button>
          </form>
        </details>
      )}
    </section>
  );
}
