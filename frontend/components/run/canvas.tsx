"use client";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { LaneId } from "../../lib/run/contract";
import type { Card, Coin, NS, OrbMode } from "../../lib/run/fold";
import { LANE_NAME } from "../../lib/run/scenario";
import { IcCheck, IcLock } from "./icons";
import Orb from "./orb";

// The run canvas: the 5-step path on row 0, a dispute's detour on the row below, and the orb
// carrying the job back up to Produce. One CSS transform is the camera, so a new target
// retargets mid-move instead of restarting.

export interface CNode { id: string; row: number; col: number; title: string; desc: string; lane?: LaneId; keepChip?: boolean }
export interface CanvasView {
  status: Record<string, NS>;
  chip: Record<string, string | undefined>;
  orb: { node: string; mode: OrbMode } | null;
  coin: Coin | null;
  loops: string[]; // lane node ids whose work was carried back to Produce
  cards: Card[];
}
export type Focus = { kind: "overview" } | { kind: "follow" };

export const COL_X = (c: number) => 40 + c * 240;
export const ROW_Y = [40, 220, 390, 560];
export const W = 180, H = 54;
const cx = (n: CNode) => COL_X(n.col) + W / 2;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const CHIP: Record<string, string> = { running: "Running", done: "Done", waiting: "Waiting", fail: "Our miss", grey: "Grey area" };

export default function Canvas({ nodes, view, focus, panelOpen, onNode, overlay, quiet }: {
  nodes: CNode[]; view: CanvasView; focus: Focus; panelOpen: boolean; onNode: (id: string) => void; overlay?: ReactNode; quiet?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1100, h: 600 });
  useLayoutEffect(() => {
    const el = box.current!;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el); setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const st = (id: string): NS => view.status[id] ?? "idle";
  const orbNode = (view.orb && byId[view.orb.node]) ?? nodes[0];
  const rows = [...new Set(nodes.map((n) => n.row))].filter((r) => r > 0);
  const maxRow = Math.max(0, ...rows);
  const WW = COL_X(4) + W + 40;
  const WH = ROW_Y[maxRow] + H + 110;

  // camera
  let s: number, tx: number, ty: number;
  if (focus.kind === "overview") {
    s = Math.min((size.w - 40) / WW, (size.h - 90) / WH, 1.1);
    tx = (size.w - WW * s) / 2; ty = Math.max(10, (size.h - 70 - WH * s) / 2);
  } else {
    const vw = panelOpen ? size.w - 460 : size.w;
    // never below 1: the smallest text stays 12px on screen, the camera pans instead
    s = clamp(Math.min((vw - 48) / WW, (size.h - 110) / WH), 1, 1.15);
    tx = WW * s <= vw - 48 ? (vw - WW * s) / 2 : clamp(vw / 2 - cx(orbNode) * s, vw - WW * s - 24, 24);
    ty = WH * s <= size.h - 90 ? (size.h - 70 - WH * s) / 2 : clamp(size.h / 2 - (ROW_Y[orbNode.row] + 40) * s, size.h - WH * s - 70, 20);
  }

  const byRow = (r: number) => nodes.filter((n) => n.row === r).sort((a, b) => a.col - b.col);
  const pairs = (list: CNode[]) => list.slice(1).map((b, i) => [list[i], b] as const);
  const seq = [byRow(0), ...rows.map(byRow)].flatMap(pairs);
  const straight = (a: CNode, b: CNode) => `M${COL_X(a.col) + W} ${ROW_Y[a.row] + H / 2} H${COL_X(b.col)}`;
  const on = (a: string, b: string) => !["idle", "running", "waiting"].includes(st(a)) && st(b) !== "idle";
  const review = byId.review, produce = byId.produce;
  const branch = (row: number) => `M${cx(review)} ${ROW_Y[0] + H} V${ROW_Y[1] - 50} H20 V${ROW_Y[row] + H / 2} H40`;
  const back = (n: CNode) => {
    const x2 = COL_X(produce.col) + W - 24, x1 = n.col === produce.col ? x2 : cx(n), y1 = ROW_Y[n.row];
    return x1 === x2 ? `M${x1} ${y1} V${ROW_Y[0] + H + 4}` : `M${COL_X(n.col) + W} ${y1 + H / 2} H${x2} V${ROW_Y[0] + H + 4}`;
  };
  const single = rows.length === 1 ? byRow(rows[0]) : null;
  const last = single ? single[single.length - 1] : null;

  return (
    <div className="cv" ref={box}>
      <div className="cv-world" style={{ width: WW, height: WH, transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
        {rows.map((r) => {
          const lane = byRow(r)[0].lane!;
          return <div key={r} className={`band band-${lane}`} style={{ top: ROW_Y[r] - 44 }}><span className="band-label">{LANE_NAME[lane]}</span></div>;
        })}
        <svg className="edges" width={WW} height={WH} aria-hidden>
          <defs>
            <marker id="arr" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M1 1 L7 4 L1 7" fill="none" stroke="var(--blue)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </marker>
          </defs>
          {rows.map((r) => {
            const d = branch(r); const live = st(byRow(r)[0].id) !== "idle";
            return <g key={r}><path d={d} className="edge" /><path d={d} pathLength={1} className={`edge-on${live ? " on" : ""}`} /></g>;
          })}
          {seq.map(([a, b]) => {
            const d = straight(a, b);
            return <g key={a.id + b.id}><path d={d} className="edge" /><path d={d} pathLength={1} className={`edge-on${on(a.id, b.id) ? " on" : ""}`} /></g>;
          })}
          {last && <path d={back(last)} className="edge ghost" />}
          {last && view.loops.includes(last.id) && <path key={last.id} d={back(last)} pathLength={1} className="loop" markerEnd="url(#arr)" />}
        </svg>
        {last && !view.loops.includes(last.id) && <span className="back-label" style={{ transform: `translate(${COL_X(produce.col) + W - 16}px, ${ROW_Y[0] + H + 34}px)` }}>back to Produce</span>}

        {nodes.map((n) => {
          const ns = st(n.id);
          const cards = view.cards.filter((c) => c.node === n.id);
          const here = view.orb?.node === n.id;
          const showChip = ns !== "idle" && (!quiet || n.keepChip);
          const chip = view.chip[n.id] ?? CHIP[ns];
          return (
            <div key={n.id} className={`nd n-${ns}`} style={{ transform: `translate(${COL_X(n.col)}px, ${ROW_Y[n.row]}px)` }}
              role="button" tabIndex={0} onClick={() => onNode(n.id)} onKeyDown={(e) => { if (e.key === "Enter") onNode(n.id); }} aria-label={`${n.title}, ${ns}`}>
              {showChip && <span key={ns + chip} className={`chip c-${ns}`}>{ns === "done" ? <IcCheck size={11} strokeWidth={2.4} /> : ns === "running" ? <i className="spin2" /> : <i className="sqd" />}{chip}</span>}
              <span className="nd-t">{n.title}</span>
              <span className="nd-d">{n.desc}</span>
              {!quiet && cards.length > 0 && (here || cards.some((c) => c.tone === "rule")) && (
                <div className="ev-stack">{cards.filter((c) => here || c.tone === "rule").map((c, i) => <span key={c.id} className={`ev ev-${c.tone}`} style={{ transitionDelay: `${i * 90}ms` }}>{c.text}</span>)}</div>
              )}
            </div>
          );
        })}

        {!quiet && view.orb && (
          <div className="orb-wrap" style={{ transform: `translate(${COL_X(orbNode.col) + 6}px, ${ROW_Y[orbNode.row] + H + 6}px)` }}>
            <Orb mode={view.orb.mode} />
            {view.coin && <span className={`coin${view.coin.locked ? " locked" : ""}${view.coin.done ? " done" : ""}`}>
              {view.coin.locked ? <IcLock size={10} strokeWidth={2} /> : view.coin.done ? <IcCheck size={10} strokeWidth={2.4} /> : <i className="coin-dot" />}{view.coin.text}</span>}
          </div>
        )}
      </div>
      {overlay}
    </div>
  );
}
