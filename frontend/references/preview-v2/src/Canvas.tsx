import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Check, Lock, ScrollText } from "lucide-react";
import { COL_X, H, ROW_Y, W, laneOf, type Lane, type Node, type View } from "./timeline";

export type Focus = { kind: "overview" } | { kind: "follow" };

const cx = (n: Node) => COL_X(n.col) + W / 2;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const CHIP: Record<string, string> = { running: "Running", done: "Done", waiting: "Waiting", fail: "Our miss", grey: "Grey area" };
const VERDICTS = ["rV", "gV", "aG"];

function Orb({ mode }: { mode: string }) {
  return (
    <span className={`orb orb-${mode}`} aria-hidden>
      {mode === "carry" && <span className="orb-sheet"><ScrollText size={10} strokeWidth={1.8} /></span>}
      <svg viewBox="0 0 28 28" width="28" height="28">
        <circle cx="14" cy="14" r="13" className="orb-body" />
        <g className="orb-eyes">
          <rect x="8.6" y="10" width="3.2" height="6.4" rx="1.6" />
          <rect x="16.2" y="10" width="3.2" height="6.4" rx="1.6" />
        </g>
      </svg>
    </span>
  );
}

export default function Canvas({ nodes, view, focus, panelOpen, laneTone, onNode, overlay, quiet }: {
  nodes: Node[]; view: View; focus: Focus; panelOpen: boolean; laneTone: Record<Lane, string>;
  onNode: (id: string) => void; overlay?: ReactNode; quiet?: boolean;
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
  const st = (id: string) => view.status[id] ?? "idle";
  const orbNode = byId[view.orb.node] ?? nodes[0];
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
    s = clamp(Math.min((vw - 48) / WW, (size.h - 110) / WH), 0.9, 1.15);
    tx = WW * s <= vw - 48 ? (vw - WW * s) / 2 : clamp(vw / 2 - cx(orbNode) * s, vw - WW * s - 24, 24);
    ty = WH * s <= size.h - 90 ? (size.h - 70 - WH * s) / 2 : clamp(size.h / 2 - (ROW_Y[orbNode.row] + 40) * s, size.h - WH * s - 70, 20);
  }

  const byRow = (r: number) => nodes.filter((n) => n.row === r).sort((a, b) => a.col - b.col);
  const pairs = (list: Node[]) => list.slice(1).map((b, i) => [list[i], b] as const);
  const seq = [byRow(0), ...rows.map(byRow)].flatMap(pairs);
  const straight = (a: Node, b: Node) => `M${COL_X(a.col) + W} ${ROW_Y[a.row] + H / 2} H${COL_X(b.col)}`;
  const on = (a: string, b: string) => !["idle", "running", "waiting"].includes(st(a)) && st(b) !== "idle";
  const review = byId.s5, produce = byId.s3;
  const branch = (row: number) => `M${cx(review)} ${ROW_Y[0] + H} V${ROW_Y[1] - 50} H20 V${ROW_Y[row] + H / 2} H40`;
  const back = (n: Node) => {
    const x2 = COL_X(produce.col) + W - 24, x1 = n.col === produce.col ? x2 : cx(n), y1 = ROW_Y[n.row];
    return x1 === x2 ? `M${x1} ${y1} V${ROW_Y[0] + H + 4}` : `M${COL_X(n.col) + W} ${y1 + H / 2} H${x2} V${ROW_Y[0] + H + 4}`;
  };
  const single = rows.length === 1 ? byRow(rows[0]) : null;
  const last = single ? single[single.length - 1] : null;

  return (
    <div className="cv" ref={box}>
      <div className="cv-world" style={{ width: WW, height: WH, transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
        {rows.map((r) => {
          const lane = laneOf(byRow(r)[0].id)!;
          return <div key={r} className={`band band-${lane}`} style={{ top: ROW_Y[r] - 44 }}><span className="band-label">{laneTone[lane]}</span></div>;
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
          const here = view.orb.node === n.id;
          const showChip = ns !== "idle" && (!quiet || VERDICTS.includes(n.id));
          return (
            <div key={n.id} className={`nd n-${ns}`} style={{ transform: `translate(${COL_X(n.col)}px, ${ROW_Y[n.row]}px)` }}
              role="button" tabIndex={0} onClick={() => onNode(n.id)} onKeyDown={(e) => { if (e.key === "Enter") onNode(n.id); }} aria-label={`${n.title}, ${ns}`}>
              {showChip && <span key={ns + (view.chip[n.id] ?? "")} className={`chip c-${ns}`}>{ns === "done" ? <Check size={11} strokeWidth={2.4} /> : ns === "running" ? <i className="spin2" /> : <i className="sqd" />}{view.chip[n.id] ?? CHIP[ns]}</span>}
              <span className="nd-t">{n.title}</span>
              <span className="nd-d">{n.desc}</span>
              {!quiet && cards.length > 0 && (here || cards.some((c) => c.tone === "rule")) && (
                <div className="ev-stack">{cards.map((c, i) => <span key={c.id} className={`ev ev-${c.tone}`} style={{ transitionDelay: `${i * 90}ms` }}>{c.text}</span>)}</div>
              )}
            </div>
          );
        })}

        {!quiet && (
          <div className="orb-wrap" style={{ transform: `translate(${COL_X(orbNode.col) + 6}px, ${ROW_Y[orbNode.row] + H + 6}px)` }}>
            <Orb mode={view.orb.mode} />
            {view.coin && <span className={`coin${view.coin.locked ? " locked" : ""}${view.coin.done ? " done" : ""}`}>
              {view.coin.locked ? <Lock size={10} strokeWidth={2} /> : view.coin.done ? <Check size={10} strokeWidth={2.4} /> : <i className="coin-dot" />}{view.coin.text}</span>}
          </div>
        )}
      </div>
      {overlay}
    </div>
  );
}
