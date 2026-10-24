"use client";
import { useState } from "react";
import type { Binding, ControllerAction, Step } from "../../lib/run/contract";
import { coinFor, draftedFor, linesFor, type NodeState, type RunState } from "../../lib/run/fold";
import { CO } from "../../lib/run/scenario";
import { Books, Deadline, EvidenceCard, LearnedNote, RuleCard, Sheet, VerdictNote, type OnSource } from "./cards";
import Chat, { type ChatContext } from "./chat";
import Checklist, { statusOf } from "./checklist";

// A step's context, shown inline on the canvas when you zoom into it. Renders whatever the event
// stream attached to the step, so there is no per-step layout to keep in sync.

export type Highlight = { messageId: string } | { row: string };
export type Decide = (action: ControllerAction, binding: Binding) => Promise<string | null>;

const ACTIONS: [ControllerAction, string][] = [["approve", "Yoga counts"], ["reject", "Not in scope"], ["ask", "Ask for more"], ["escalate", "Send up"]];

export default function StepDetail({ step, node, run, track, highlight, onSource, decide, binding }: {
  step: Step; node: NodeState; run: RunState; track: Parameters<typeof linesFor>[1]; highlight?: Highlight; onSource?: OnSource; decide?: Decide; binding: Binding;
}) {
  const lines = linesFor(run, track);
  const checked = step.kind === "check" ? lines : lines.filter((l) => l.id in node.checks);
  const next = node.status === "running" ? lines.find((l) => !(l.id in node.checks)) : undefined;
  const contract = node.contract ?? node.amendment;
  const ctx: ChatContext = {
    drafted: draftedFor(run, track), checks: run.nodes[`${track}/check`]?.checks ?? {}, evidence: run.evidence,
    // the last node holding a version is the delivered file; produce holds the raw dataset first
    deliveryOf: (v) => Object.values(run.nodes).map((n) => n.delivery).findLast((d) => d?.version === v),
  };
  const msgHl = highlight && "messageId" in highlight ? highlight.messageId : undefined;
  const rowHl = highlight && "row" in highlight ? highlight.row : undefined;
  // Evidence a reply already cites inline is not repeated as a loose card
  const cited = new Set(node.messages.flatMap((m) => m.attach?.flatMap((a) => (a.kind === "evidence" ? [a.evidenceId] : [])) ?? []));
  const loose = node.evidence.filter((e) => !cited.has(e.id));
  const empty = !node.messages.length && !checked.length && !loose.length && !contract && !node.delivery && !node.verdict && !node.entries && !node.ruleApplied;
  const review = step.kind === "controller" && (node.status === "waiting" || node.decision);

  return (
    <div className="detail-body">
      {empty && <p className="faint">{node.status === "idle" ? "Not started yet." : "Working on it."}</p>}
      {node.messages.length > 0 && <Chat messages={node.messages} ctx={ctx} highlight={msgHl} onSource={onSource} />}
      {review && decide && <ControllerReview node={node} decide={decide} binding={binding} />}
      {loose.map((e) => <EvidenceCard key={e.id} e={e} onSource={onSource} />)}
      {node.verdict && <VerdictNote v={node.verdict} />}
      {node.ruleApplied && <LearnedNote {...node.ruleApplied} />}
      {node.rule && <RuleCard rule={node.rule} />}
      {contract && (
        <section>
          <div className="sec-k">{node.contract ? `Data contract v${node.contract.version}` : node.amendment!.summary} · ${node.contract?.price ?? node.amendment!.price}</div>
          <ol className="lines">{contract.lines.map((l) => <li key={l.id}>{l.text}</li>)}</ol>
        </section>
      )}
      {checked.length > 0 && (
        <Checklist title="Contract checks" items={checked.map((line) => {
          const c = node.checks[line.id];
          return { line, status: statusOf(line, node.checks, next), detail: c?.fix ? `${c.reason}. ${c.fix}.` : c?.reason };
        })} />
      )}
      {node.delivery && <Sheet d={node.delivery} highlight={rowHl} />}
      {node.delivery?.reviewClosesAt && <Deadline closesAt={node.delivery.reviewClosesAt} />}
      {node.entries && node.margin && <Books entries={node.entries} margin={node.margin} coin={coinFor(run, track)} />}
      {node.allowedBy.length > 0 && <p className="allowed faint">Allowed by: {node.allowedBy.join(" · ")}</p>}
    </div>
  );
}

/** The controller's seat: the question, the evidence, and what she can do. */
function ControllerReview({ node, decide, binding }: { node: NodeState; decide: Decide; binding: Binding }) {
  const [busy, setBusy] = useState<ControllerAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const act = async (a: ControllerAction) => {
    setBusy(a); setError(null);
    const err = await decide(a, binding);
    setBusy(null); setError(err);
  };
  const waiting = node.status === "waiting";
  return (
    <section className="review">
      <div className="sec-k">{waiting ? `Waiting on ${node.waitingOn}` : `${node.decision?.by} decided`}</div>
      {node.decision && !waiting && <p>{node.decision.note}</p>}
      {waiting && (
        <div className="review-actions">
          {ACTIONS.map(([a, label]) => (
            <button key={a} type="button" className={`btn${a === "approve" ? " solid" : ""}`} disabled={busy !== null} onClick={() => act(a)}>{label}</button>
          ))}
        </div>
      )}
      {error && <p className="review-err">{error}</p>}
      <p className="ev-note">Decided as {CO.controller}, controller. The decision, the evidence version and the time are recorded.</p>
    </section>
  );
}
