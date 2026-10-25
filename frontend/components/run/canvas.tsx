"use client";
import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import type { LaneId, SourceLine } from "../../lib/run/contract";
import type { Card, Coin, NS, OrbMode } from "../../lib/run/fold";
import { LANE_NAME } from "../../lib/run/scenario";
import { IcCheck, IcCoin, IcLock } from "./icons";
import Label from "./label";
import Orb from "./orb";
import Warehouse from "./warehouse";

// The run canvas: the 5-step path on row 0, a dispute's detour on the row below, and the orb
// carrying the job back up to Produce. One CSS transform is the camera, so a new target
// retargets mid-move instead of restarting. Dragging or scrolling frees the camera; it stays
// where the viewer put it until Play, Replay or another case hands it back to the orb.

export interface CNode { id: string; row: number; col: number; title: string; desc: string; lane?: LaneId; keepChip?: boolean }
export interface CanvasView {
  status: Record<string, NS>;
  chip: Record<string, string | undefined>;
  orb: { node: string; mode: OrbMode } | null;
  coin: Coin | null;
  loops: string[]; // lane node ids whose work was carried back to Produce
  cards: Card[];
  source?: { node: string; lines: SourceLine[] } | null; // what the agent reads at the source during a dispute
}
export type Focus = { kind: "overview" } | { kind: "follow" };

export const COL_X = (c: number) => 40 + c * 240;
export const ROW_Y = [40, 220, 390, 560];
export const W = 200, H = 54;
const cx = (n: CNode) => COL_X(n.col) + W / 2;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
// iOS's rubber band: past an edge the world still follows, less the further it is pulled
const band = (v: number, [lo, hi]: Range, dim: number) => {
  const pull = (d: number) => (1 - 1 / ((d * 0.55) / dim + 1)) * dim;
  return v < lo ? lo - pull(lo - v) : v > hi ? hi + pull(v - hi) : v;
};
const CHIP: Record<string, string> = { running: "Running", done: "Done", waiting: "Waiting", fail: "Our miss", grey: "Grey area" };
type Cam = { tx: number; ty: number; s: number };
type Range = readonly [number, number];
const T = (c: Cam) => `translate(${c.tx}px, ${c.ty}px) scale(${c.s})`;

export default function Canvas({ nodes, view, focus, panelOpen, onNode, overlay, quiet, recenter }: {
  nodes: CNode[]; view: CanvasView; focus: Focus; panelOpen: boolean; onNode: (id: string) => void; overlay?: ReactNode; quiet?: boolean;
  recenter?: number; // a new value hands the camera back to the orb
}) {
  const box = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1100, h: 600 });
  const [free, setFree] = useState<Cam | null>(null);
  const [dragging, setDragging] = useState(false);
  const [still, setStill] = useState(true); // no camera glide until the first measured frame has painted: mounting (or coming back from the customer view) shouldn't pan in
  const drag = useRef<{ id: number; x: number; y: number; from: Cam; on: boolean } | null>(null);
  const pan = useRef<{ follow: Cam; bx: Range; by: Range; on: boolean }>(null);
  useLayoutEffect(() => {
    const el = box.current!;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el); setSize({ w: el.clientWidth, h: el.clientHeight });
    const settle = requestAnimationFrame(() => setStill(false));
    return () => { ro.disconnect(); cancelAnimationFrame(settle); };
  }, []);
  useEffect(() => setFree(null), [recenter, focus.kind]);
  // Wheel is native so it can preventDefault: a two-finger swipe pans instead of going back a page
  useEffect(() => {
    const el = box.current!;
    const onWheel = (e: WheelEvent) => {
      const p = pan.current;
      if (!p?.on || e.ctrlKey) return;
      e.preventDefault();
      const k = e.deltaMode === 1 ? 16 : 1;
      setFree((f) => {
        const c = f ?? p.follow, tx = clamp(c.tx - e.deltaX * k, ...p.bx), ty = clamp(c.ty - e.deltaY * k, ...p.by);
        return Math.abs(tx - c.tx) + Math.abs(ty - c.ty) < 0.5 ? f : { s: c.s, tx, ty };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const st = (id: string): NS => view.status[id] ?? "idle";
  const orbNode = (view.orb && byId[view.orb.node]) ?? nodes[0];
  const rows = [...new Set(nodes.map((n) => n.row))].filter((r) => r > 0);
  const maxRow = Math.max(0, ...rows);
  const byRow = (r: number) => nodes.filter((n) => n.row === r).sort((a, b) => a.col - b.col);
  // Progressive reveal: a step appears when the one before it starts, the next one waits ghosted for context, the rest is not there yet
  const revealed = new Set<string>(), next = new Set<string>();
  for (const r of [0, ...rows]) {
    const list = byRow(r);
    let last = -1;
    list.forEach((n, i) => { if (st(n.id) !== "idle") last = i; });
    if (r === 0) last = Math.max(last, list.findIndex((n) => n.id === orbNode.id));
    list.forEach((n, i) => { if (i <= last) revealed.add(n.id); else if (i === last + 1) next.add(n.id); });
  }
  const shown = nodes.filter((n) => revealed.has(n.id) || next.has(n.id));
  // The source sits at the end of the detour row; the orb walks over while it reads
  const srcNode = view.source ? byId[view.source.node] : undefined;
  const source = view.source && srcNode && st(srcNode.id) !== "idle" ? { lines: view.source.lines, node: srcNode, col: byRow(srcNode.row)[byRow(srcNode.row).length - 1].col + 1 } : null;
  const atSource = !!source && view.orb?.node === source.node.id && st(source.node.id) === "running";
  const orbX = atSource && source ? COL_X(source.col) + 6 : COL_X(orbNode.col) + 6;
  const orbY = ROW_Y[orbNode.row] + H + 6;
  const tunnel = useTunnel(orbX, orbY);
  const WWfull = COL_X(4) + W + 40;
  const WHfull = ROW_Y[maxRow] + H + 110;
  // the camera frames what is shown, so the run opens close on the first step and widens as the path grows
  const WW = Math.max(...shown.map((n) => COL_X(n.col) + W), source ? COL_X(source.col) + 330 : 0) + 40;
  const WH = ROW_Y[Math.max(0, ...shown.map((n) => n.row))] + H + 110;
  const DOTS = 3000; // the grid extends past the world so it fills the stage at any camera position

  // camera
  let s: number, tx: number, ty: number;
  const vw = panelOpen ? size.w - 460 : size.w;
  if (focus.kind === "overview") {
    s = Math.min((size.w - 40) / WW, (size.h - 90) / WH, 1.1);
    tx = (size.w - WW * s) / 2; ty = Math.max(10, (size.h - 70 - WH * s) / 2);
  } else {
    // never below 1.15: cards, chips and the orb stay easy to read from the back of a room; the camera pans instead
    s = clamp(Math.min((vw - 48) / WW, (size.h - 110) / WH), 1.15, 1.3);
    tx = WW * s <= vw - 48 ? (vw - WW * s) / 2 : clamp(vw / 2 - (orbX + 14) * s, vw - WW * s - 24, 24);
    ty = WH * s <= size.h - 90 ? (size.h - 70 - WH * s) / 2 : clamp(size.h / 2 - (ROW_Y[orbNode.row] + 40) * s, size.h - WH * s - 70, 20);
  }
  const cam = free ?? { tx, ty, s };
  // A world wider than the view slides edge to edge; one that fits only gives a little, then springs back
  const range = (t: number, world: number, view: number, pad: number): Range => (world > view - 2 * pad ? [view - pad - world, pad] : [t, t]);
  const bx = range(tx, WW * cam.s, vw, 24), by = range(ty, WH * cam.s, size.h - 70, 20);
  const pannable = focus.kind === "follow";
  useLayoutEffect(() => { pan.current = { follow: { tx, ty, s }, bx, by, on: pannable }; });

  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    if (!pannable || e.button !== 0 || drag.current || (e.target as Element).closest("button, .caption")) return;
    drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY, from: cam, on: false };
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || e.pointerId !== d.id) return; // a second finger never takes over the drag
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (!d.on) {
      if (Math.hypot(dx, dy) < 4) return; // still a click on whatever was pressed
      d.on = true; e.currentTarget.setPointerCapture(e.pointerId); setDragging(true);
    }
    setFree({ s: d.from.s, tx: band(d.from.tx + dx, bx, vw), ty: band(d.from.ty + dy, by, size.h) });
  };
  const onUp = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || e.pointerId !== d.id) return;
    drag.current = null;
    if (!d.on || !free) return;
    setDragging(false);
    const to = { s: free.s, tx: clamp(free.tx, ...bx), ty: clamp(free.ty, ...by) };
    if ((to.tx !== free.tx || to.ty !== free.ty) && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const ease = getComputedStyle(document.documentElement).getPropertyValue("--ease-out");
      world.current?.animate([{ transform: T(free) }, { transform: T(to) }], { duration: 320, easing: ease });
    }
    // sprang all the way back onto the orb: keep following it
    setFree(to.tx === tx && to.ty === ty && to.s === s ? null : to);
  };

  const pairs = (list: CNode[]) => list.slice(1).map((b, i) => [list[i], b] as const);
  const shownPair = (a: CNode, b: CNode) => revealed.has(a.id) && (revealed.has(b.id) || next.has(b.id));
  const seq = [byRow(0), ...rows.map(byRow)].flatMap(pairs);
  const straight = (a: CNode, b: CNode) => `M${COL_X(a.col) + W} ${ROW_Y[a.row] + H / 2} H${COL_X(b.col)}`;
  const on = (a: string, b: string) => !["idle", "running", "waiting"].includes(st(a)) && st(b) !== "idle";
  const review = byId.review, produce = byId.produce;
  // Detours follow the same reveal rules as straight edges: never point into empty space.
  // Human review can appear before customer review (for example, after failed funding).
  const branches = review ? rows.filter((r) => shownPair(review, byRow(r)[0])) : [];
  // The branch runs under the detour row and comes up into its first step, so it never crosses the return arrow
  const branch = (row: number) => `M${cx(review)} ${ROW_Y[0] + H} V${ROW_Y[row] + H + 50} H20 V${ROW_Y[row] + H / 2} H40`;
  const back = (n: CNode) => {
    const x2 = COL_X(produce.col) + W - 24, x1 = n.col === produce.col ? x2 : cx(n), y1 = ROW_Y[n.row];
    return x1 === x2 ? `M${x1} ${y1} V${ROW_Y[0] + H + 4}` : `M${COL_X(n.col) + W} ${y1 + H / 2} H${x2} V${ROW_Y[0] + H + 4}`;
  };
  const single = rows.length === 1 ? byRow(rows[0]) : null;
  const end = single?.[single.length - 1];
  const last = end && produce && revealed.has(end.id) && revealed.has(produce.id) ? end : null;

  return (
    <>
      <div className={`cv${pannable ? " pannable" : ""}${dragging ? " dragging" : ""}${free ? " free" : ""}${still ? " still" : ""}`} ref={box}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
        <div className="cv-world" ref={world} style={{ width: WWfull, height: WHfull, transform: T(cam) }}>
          <div className="cv-dots" style={{ inset: -DOTS }} aria-hidden />
          {rows.map((r) => {
            const lane = byRow(r)[0].lane!;
            return <div key={r} className={`band band-${lane}`} style={{ top: ROW_Y[r] - 44 }}><span className="band-label">{lane ? LANE_NAME[lane] : "Evidence review"}</span></div>;
          })}
          <svg className="edges" width={WWfull} height={WHfull} aria-hidden>
            <defs>
              <marker id="arr" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M1 1 L7 4 L1 7" fill="none" stroke="var(--blue)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </marker>
            </defs>
            {branches.map((r) => {
              const d = branch(r); const live = st(byRow(r)[0].id) !== "idle";
              return <g key={r}><path d={d} className="edge" /><path d={d} pathLength={1} className={`edge-on${live ? " on" : ""}`} /></g>;
            })}
            {seq.map(([a, b]) => {
              const d = straight(a, b);
              return <g key={a.id + b.id} className={shownPair(a, b) ? undefined : "hid"}><path d={d} className="edge" /><path d={d} pathLength={1} className={`edge-on${on(a.id, b.id) ? " on" : ""}`} /></g>;
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
            const vis = revealed.has(n.id) ? "" : next.has(n.id) ? " n-next" : " n-hidden";
            return (
              <div key={n.id} className={`nd n-${ns}${vis}`} style={{ transform: `translate(${COL_X(n.col)}px, ${ROW_Y[n.row]}px)` }} aria-hidden={vis === " n-hidden" || undefined}
                role="button" tabIndex={vis ? -1 : 0} onClick={() => onNode(n.id)} onKeyDown={(e) => { if (e.key === "Enter") onNode(n.id); }} aria-label={`${n.title}, ${ns}`}>
                {showChip && <span key={ns + chip} className={`chip c-${ns}`}>{ns === "done" ? <IcCheck size={11} strokeWidth={2.4} /> : ns === "running" ? <i className="spin2" /> : <i className="sqd" />}<Label text={chip} quiet="tail" /></span>}
                <span className="nd-t">{n.title}</span>
                <span className="nd-d"><Label text={n.desc} quiet="tail" /></span>
                {!quiet && cards.length > 0 && (here || cards.some((c) => c.tone === "rule")) && n.id !== source?.node.id && (
                  <div className="ev-stack">{cards.filter((c) => here || c.tone === "rule").map((c, i) => <span key={c.id} className={`ev ev-${c.tone}`} style={{ transitionDelay: `${i * 90}ms` }}><Label text={c.text} /></span>)}</div>
                )}
              </div>
            );
          })}
  
          {source && (
            <div className="src" style={{ transform: `translate(${COL_X(source.col)}px, ${ROW_Y[source.node.row]}px)` }}>
              <span className="src-glyph"><Warehouse /></span>
              <div className="src-lines">{source.lines.map((l, i) => <span key={l.id} className={`src-l${l.checked ? " ok" : ""}`} style={{ transitionDelay: `${i * 60}ms` }}>{l.checked ? <IcCheck size={11} strokeWidth={2.4} /> : <i className="spin2" />}<Label text={l.text} quiet="tail" /></span>)}</div>
            </div>
          )}
          {!quiet && view.orb && (
            <div className={`orb-wrap${tunnel.phase ? ` tunnel-${tunnel.phase}` : ""}`} style={{ transform: `translate(${tunnel.x}px, ${tunnel.y}px)` }}>
              <Orb mode={view.orb.mode} found={view.orb.mode === "inspect" ? view.cards.some((c) => c.node === view.orb!.node && c.tone === "ev") : undefined} />
              {view.coin && <span className={`coin${view.coin.locked ? " locked" : ""}${view.coin.done ? " done" : ""}`}>
                <span key={view.coin.text} className="coin-t">{view.coin.locked ? <IcLock size={10} strokeWidth={2} /> : view.coin.done ? <IcCheck size={10} strokeWidth={2.4} /> : <IcCoin />}<Label text={view.coin.text} quiet="tail" /></span></span>}
            </div>
          )}
        </div>
      </div>
      {/* outside .cv so its edge fade never touches it */}
      {overlay}
    </>
  );
}

// The groundhog doesn't slide between steps: it ducks into its hole, the hole closes, it stays
// underground for a beat, and it pops up out of a new hole at the next step. Reduced motion just
// moves it.
const DIVE_MS = 820; // dive 600ms, then the hole closes by ~800ms
const UNDERGROUND_MS = 760; // the beat it spends tunnelling before the new hole opens
function useTunnel(x: number, y: number) {
  const [state, setState] = useState<{ x: number; y: number; phase: "" | "down" | "hidden" }>({ x, y, phase: "" });
  const target = useRef({ x, y });
  useEffect(() => {
    if (target.current.x === x && target.current.y === y) return;
    target.current = { x, y };
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setState({ x, y, phase: "" });
      return;
    }
    let raf = 0;
    setState((s) => ({ ...s, phase: "down" }));
    const pop = window.setTimeout(() => {
      setState({ x, y, phase: "hidden" });
      raf = requestAnimationFrame(() => (raf = requestAnimationFrame(() => setState({ x, y, phase: "" }))));
    }, DIVE_MS + UNDERGROUND_MS);
    return () => { window.clearTimeout(pop); cancelAnimationFrame(raf); };
  }, [x, y]);
  return state;
}
