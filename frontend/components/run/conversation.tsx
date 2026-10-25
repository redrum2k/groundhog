"use client";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Evidence, Message, Source } from "../../lib/run/contract";
import type { View } from "../../lib/run/fold";
import { S } from "../../lib/run/scenario";
import { IcCheck, IcChevronRight } from "./icons";
import { OrbSlot, type Stop } from "./guide";
import Label from "./label";

// Shared presentation for recorded, retained-broker and funded aggregate conversations.
// The caller supplies messages, decisions and actions; these components do not run a scenario.
export function CiteChip({ e, onCite }: { e: Evidence; onCite: (s: Source) => void }) {
  return <button className="cite" onClick={() => onCite(e.source)}><Label text={e.label} /><IcChevronRight size={11} strokeWidth={1.8} /></button>;
}

/** `guide`: the customer view's orb sits beside our agent's newest message (outside that view the slot renders nothing). */
export function Chat({ items, view, highlight, onCite, guide }: { items: Message[]; view: View; highlight?: string; onCite: (s: Source) => void; guide?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const seen = useRef(items.length);
  const height = useRef(0); // the pane's scroll height before the latest messages landed
  // New messages glide into view unless the viewer had scrolled up to reread earlier ones.
  // Judged against the height before this batch, so a burst of bubbles never reads as the viewer scrolling away.
  useEffect(() => {
    const added = items.length > seen.current;
    seen.current = items.length;
    const last = box.current?.lastElementChild as HTMLElement | null | undefined;
    const pane = box.current?.closest(".cust-body, .panel-b, .customer");
    if (!last || !pane) return;
    const following = height.current - pane.scrollTop - pane.clientHeight < 160;
    height.current = pane.scrollHeight;
    if (!added || !following) return;
    const below = last.getBoundingClientRect().bottom - pane.getBoundingClientRect().bottom;
    if (below > 0) pane.scrollBy?.({ top: below + 12, behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [items.length]);
  const newest = guide ? items.findLast((m) => m.from === "agent")?.id : undefined;
  return (
    <div className="chat" ref={box}>
      {items.map((m) => (
        <div key={m.id} id={`msg-${m.id}`} className={`bub b-${m.from}${highlight === m.id ? " flash" : ""}`}>
          {m.id === newest && <OrbSlot name="transcript" />}
          <span className="bub-who">{m.from === "buyer" ? S.buyerAgent : m.from === "controller" ? <Label text={`${S.controller} · ${S.controllerRole}`} quiet="tail" /> : S.agent}</span>
          <div className="bub-text">
            {m.text}
            {[...new Set((m.attach ?? []).flatMap(a=>a.kind==="evidence"?[a.evidenceId]:[]))].map(id=>view.evidence[id] ? <span key={id}> <CiteChip e={view.evidence[id]} onCite={onCite} /></span> : null)}
          </div>
        </div>
      ))}
    </div>
  );
}

/** One of Summit's decisions: the thing to decide on, the buttons while it's open, the choice once made. */
/** `done` is the move just made here: the card keeps its place and its height, the receipt where the buttons were. */
export function Decision({ title, open, taken, done, slot = "decision", orb, children, actions }: { title: string; open: boolean; taken?: ReactNode; done?: string; slot?: Stop; orb?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  if (!open && !done && taken) return (
    <details className="decision taken">
      <summary className="decision-h"><IcChevronRight size={12} strokeWidth={2} className="chev" /><span className="decision-taken"><IcCheck size={12} strokeWidth={2.2} /> {taken}</span><span className="decision-t">{title}</span></summary>
      <div className="decision-body">{children}</div>
    </details>
  );
  return (
    <section className={`decision${open || done ? " open" : ""}`}>
      <div className="decision-h"><span className="decision-t">{title}</span>{(open || done) && <OrbSlot name={slot} orb={orb} />}</div>
      {children}
      {done ? <div className="decision-actions"><span className="decision-taken decision-done"><IcCheck size={12} strokeWidth={2.2} /> {done}</span></div>
        : open && actions && <div className="decision-actions">{actions}</div>}
    </section>
  );
}

/** A stretch of the conversation: open and scrolling in its own box while it is the live thing, folded once the decision it fed is taken. */
/** `compact`: it stays open but short, pinned to the latest turn, so the decision it fed stays in view. */
export function Transcript({ title, count, open, compact, children }: { title: string; count?: number; open: boolean; compact?: boolean; children: ReactNode }) {
  return <TranscriptBody key={String(open)} title={title} count={count} open={open} compact={compact}>{children}</TranscriptBody>;
}

function TranscriptBody({ title, count, open, compact, children }: { title: string; count?: number; open: boolean; compact?: boolean; children: ReactNode }) {
  const body = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (compact && body.current) body.current.scrollTop = body.current.scrollHeight; }, [compact]);
  const [isOpen, setOpen] = useState(open); // the viewer's toggle wins until the section changes state
  return (
    <details className="cust-sec" open={isOpen} onToggle={(e) => { const o = e.currentTarget.open; if (o !== isOpen) setOpen(o); }}>
      <summary className="cust-step"><IcChevronRight size={12} strokeWidth={2} className="chev" />{title}{count ? <span className="faint">{count} {count === 1 ? "turn" : "turns"}</span> : null}</summary>
      <div className={`cust-body${compact ? " short" : ""}`} ref={body}>{children}</div>
    </details>
  );
}
