"use client";
import type { ContractLine, Delivery, Evidence, Message } from "../../lib/run/contract";
import type { Check } from "../../lib/run/fold";
import { EvidenceCard, Sheet, type OnSource } from "./cards";
import Checklist, { statusOf } from "./checklist";
import { OrbMark } from "./orb";

// The conversation inside a step, with what each line carries: the contract checklist as it is
// drafted, an evidence card the reply cites, or a few rows of the delivered file.

export interface ChatContext {
  drafted: ContractLine[]; // contract lines drafted so far on this track
  checks: Record<string, Check>; // results for those lines, if any
  evidence: Record<string, Evidence>;
  deliveryOf: (version: number) => Delivery | undefined;
}

export default function Chat({ messages, ctx, highlight, onSource }: { messages: Message[]; ctx: ChatContext; highlight?: string; onSource?: OnSource }) {
  return (
    <ol className="chat">
      {messages.map((m) => (
        <li key={m.id} id={`msg-${m.id}`} className={`said${m.id === highlight ? " hl" : ""}`}>
          {m.from === "agent" ? <OrbMark /> : <span className="av" aria-hidden>{m.name[0]}</span>}
          <div className="said-b">
            <div className="who">{m.name}</div>
            <p>{m.text}</p>
            {m.attach?.map((a, i) => {
              if (a.kind === "checklist") return <Checklist key={i} title="Data contract" items={ctx.drafted.map((line) => ({ line, status: statusOf(line, ctx.checks) }))} />;
              if (a.kind === "evidence") { const e = ctx.evidence[a.evidenceId]; return e ? <EvidenceCard key={i} e={e} onSource={onSource} /> : null; }
              const d = ctx.deliveryOf(a.version);
              return d ? <Sheet key={i} d={d} rows={a.rows} title={`${d.file}, the rows in question`} /> : null;
            })}
          </div>
        </li>
      ))}
    </ol>
  );
}
