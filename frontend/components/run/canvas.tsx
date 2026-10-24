"use client";
import { useEffect, useLayoutEffect, useRef, useState, type ComponentType } from "react";
import type { Binding, LaneId, Source, Step, StepKind, Track } from "../../lib/run/contract";
import { bindingFor, coinFor, locate, nodeKey, type NodeState, type RunState } from "../../lib/run/fold";
import { CO, LANE_IF, LANE_NAME, LANES, VERDICT_LANE } from "../../lib/run/scenario";
import { EvidenceCard, RuleCard } from "./cards";
import {
  IcChat, IcCheck, IcChecklist, IcClock, IcContract, IcDeliver, IcDispute, IcLearned, IcLedger, IcPrice, IcRequest, IcScale, IcSearch, IcSheet,
  IcSignoff, type IconProps,
} from "./icons";
import Orb, { type Mood } from "./orb";
import StepDetail, { type Decide, type Highlight } from "./step-detail";

// Attio-style run canvas: the shared path once, then three stacked lanes for the ways a dispute
// can go. Nodes are laid out from the plan in the event stream. The camera is one CSS transform,
// so a new target retargets mid-move instead of restarting.

export type View =
  | { kind: "overview" }
  | { kind: "lane"; lane: LaneId }
  | { kind: "node"; key: string }
  | { kind: "follow" }
  | { kind: "source"; source: Source; back: View }; // a citation: the node that holds it, with the line or cell marked

const W = 248, H = 60, COLW = 320, ROW = 380, PAD = 80, DETAIL_W = 480;
const DOCK = 76; // the floating controls cover the bottom of the canvas
const ROW_Y: Record<Track, number> = { red: 190, green: 190 + ROW, amber: 190 + 2 * ROW, shared: 190 + ROW };
const ICON: Record<StepKind, ComponentType<IconProps>> = {
  request: IcRequest, interview: IcChat, contract: IcContract, produce: IcSheet, check: IcChecklist, deliver: IcDeliver, review: IcClock,
  dispute: IcDispute, verdict: IcScale, investigate: IcSearch, amend: IcPrice, controller: IcSignoff, learned: IcLearned, books: IcLedger,
};
// Steps whose context is the point of the demo: while following, the camera moves in and opens them
const CLOSE_UP = new Set<StepKind>(["interview", "check", "deliver", "verdict", "investigate", "controller", "contract", "books", "learned"]);

interface Placed { track: Track; step: Step; key: string; x: number; y: number }
interface Cam { x: number; y: number; s: number }

function place(run: RunState): Placed[] {
  const lanesAt = run.tracks.shared.steps.length;
  return (["shared", ...LANES] as Track[]).flatMap((track) =>
    run.tracks[track].steps.map((step, i) => ({
      track, step, key: nodeKey(track, step.id), x: PAD + ((track === "shared" ? 0 : lanesAt) + i) * COLW, y: ROW_Y[track],
    })));
}

function links(placed: Placed[]): [Placed, Placed][] {
  const out: [Placed, Placed][] = [];
  for (const track of ["shared", ...LANES]) {
    const row = placed.filter((p) => p.track === track);
    row.slice(1).forEach((p, i) => out.push([row[i], p]));
  }
  const fork = placed.filter((p) => p.track === "shared").at(-1);
  for (const lane of LANES) {
    const first = placed.find((p) => p.track === lane);
    if (fork && first) out.push([fork, first]);
  }
  return out;
}

function edgePath(a: Placed, b: Placed) {
  const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
  if (y1 === y2) return `M${x1} ${y1} H${x2}`;
  const mid = (x1 + x2) / 2, r = 8, d = y2 > y1 ? 1 : -1;
  return `M${x1} ${y1} H${mid - r} Q${mid} ${y1} ${mid} ${y1 + r * d} V${y2 - r * d} Q${mid} ${y2} ${mid + r} ${y2} H${x2}`;
}

function fit(x0: number, y0: number, x1: number, y1: number, vw: number, vh: number, max: number): Cam {
  const s = Math.min(max, (vw - 48) / (x1 - x0), (vh - 24) / (y1 - y0));
  return { s, x: vw / 2 - ((x0 + x1) / 2) * s, y: vh / 2 - ((y0 + y1) / 2) * s };
}

function camera(view: View, placed: Placed[], lanesX: number, active: Placed | undefined, focused: Placed | undefined, detailH: number, vw: number, vh: number): Cam {
  if (focused) return fit(focused.x - 24, focused.y - 64, focused.x + DETAIL_W + 24, focused.y + H + 14 + detailH + 24, vw, vh, 1.1);
  if (view.kind === "follow" && active) return fit(active.x - 230, active.y - 120, active.x + W + 230, active.y + 260, vw, vh, 0.9);
  const lane = view.kind === "lane" ? view.lane : undefined;
  const set = lane ? placed.filter((p) => p.track === lane) : placed;
  const right = Math.max(lanesX + 3 * COLW, ...set.map((p) => p.x + W + 40));
  if (lane) return fit(lanesX - 40, ROW_Y[lane] - 150, right, ROW_Y[lane] + ROW - 130, vw, vh, 1);
  return fit(PAD - 40, ROW_Y.red - 190, right, ROW_Y.amber + ROW - 130, vw, vh, 1);
}

function moodFor(p: Placed, n: NodeState): Mood {
  if (n.status === "waiting" && p.step.kind === "controller") return "blink";
  if (p.step.kind === "investigate" && n.status !== "done") return "look";
  if (p.step.kind === "produce" && p.track !== "shared" && n.status === "running") return "carry";
  return "float";
}

function chip(n: NodeState, step: Step, lines: number): { cls: string; label: string } | null {
  if (n.status === "idle") return null;
  if (n.status === "done" && n.ruleApplied) { const lane = VERDICT_LANE[n.ruleApplied.outcome]; return { cls: `v-${lane}`, label: `${LANE_NAME[lane]} · by rule` }; }
  if (n.status === "done" && n.verdict) { const lane = VERDICT_LANE[n.verdict.kind]; return { cls: `v-${lane}`, label: LANE_NAME[lane] }; }
  if (n.status === "done") return { cls: "done", label: "Completed" };
  if (n.status === "waiting") return { cls: "waiting", label: `Waiting on ${n.waitingOn}` };
  return { cls: "running", label: step.kind === "check" ? `Checking ${Object.keys(n.checks).length} of ${lines}` : "Running" };
}

function highlightOf(source: Source): Highlight | undefined {
  if (source.kind === "message") return { messageId: source.messageId };
  if (source.kind === "cell") return { row: source.row };
  return undefined;
}

export default function Canvas({ run, view, onView, selected, liveLane, decide }: {
  run: RunState; view: View; onView: (v: View) => void; selected: "all" | LaneId; liveLane?: LaneId; decide?: Decide;
}) {
  const box = useRef<HTMLDivElement>(null);
  const detail = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1200, h: 800 });
  const [detailH, setDetailH] = useState(320);
  const [ready, setReady] = useState(false); // entrances and camera moves start after the first frame, never on load

  useLayoutEffect(() => {
    const el = box.current!;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    measure();
    let id = requestAnimationFrame(() => { id = requestAnimationFrame(() => setReady(true)); });
    return () => { ro.disconnect(); cancelAnimationFrame(id); };
  }, []);

  const placed = place(run);
  const byKey = new Map(placed.map((p) => [p.key, p]));
  const active = run.active && byKey.get(nodeKey(run.active.track, run.active.step));
  const located = view.kind === "source" ? locate(run, view.source) : null;
  const focused = view.kind === "node" ? byKey.get(view.key)
    : located ? byKey.get(located.key)
    : view.kind === "follow" && active && CLOSE_UP.has(active.step.kind) ? active : undefined;
  const highlight = view.kind === "source" ? highlightOf(view.source) : undefined;
  const lanesX = PAD + run.tracks.shared.steps.length * COLW;
  const cam = camera(view, placed, lanesX, active, focused, detailH, size.w, size.h - DOCK);
  const labelScale = Math.max(1, 0.7 / cam.s); // lane names stay readable when zoomed out
  const edges = links(placed);
  const worldW = Math.max(lanesX + 3 * COLW, ...placed.map((p) => p.x + W)) + PAD;
  const status = (p: Placed) => run.nodes[p.key].status;
  const back = (p: Placed): View => (p.track === "shared" ? { kind: "overview" } : { kind: "lane", lane: p.track });
  const fork = placed.filter((p) => p.track === "shared").at(-1);
  const binding: Binding = bindingFor(run, "amber");

  // The camera fits the open step's context, however tall it grows
  useLayoutEffect(() => {
    const el = detail.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setDetailH(el.offsetHeight));
    ro.observe(el);
    setDetailH(el.offsetHeight);
    return () => ro.disconnect();
  }, [focused?.key]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (view.kind === "source") onView(view.back);
      else if (view.kind === "node") { const p = byKey.get(view.key); onView(p ? back(p) : { kind: "overview" }); }
      else if (view.kind === "lane") onView({ kind: "overview" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const onSource = (source: Source) => { if (locate(run, source)) onView({ kind: "source", source, back: view.kind === "source" ? view.back : view }); };

  return (
    <div className={`canvas${ready ? " ready" : ""}`} ref={box}>
      <div className={`world${focused ? " focusing" : ""}`} style={{ width: worldW, height: ROW_Y.amber + ROW, transform: `translate(${cam.x}px, ${cam.y}px) scale(${cam.s})` }}>
        <div className="dots" aria-hidden />

        {fork && LANES.some((l) => run.tracks[l].steps.length) && (
          <div className="fork" style={{ transform: `translate(${lanesX - 40}px, ${ROW_Y.red - 180}px)`, scale: labelScale }}>Three ways a dispute can go</div>
        )}

        {placed.length > 0 && LANES.map((lane) => (
          <div key={lane} className={`band${selected === lane ? " on" : ""}`} onClick={() => onView({ kind: "lane", lane })}
            style={{ transform: `translate(${lanesX - 40}px, ${ROW_Y[lane] - 150}px)`, width: worldW - lanesX - PAD + 80, height: ROW }}>
            <div className="lane-head" style={{ scale: labelScale }}>
              <button className="lane-label" onClick={(e) => { e.stopPropagation(); onView({ kind: "lane", lane }); }}>
                <i className={`sq ${lane}`} />{LANE_NAME[lane]}
                <span className={`tag${liveLane === lane ? " live" : ""}`}>{liveLane === lane ? "Live" : lane === "amber" ? "Rehearsal" : "Recorded"}</span>
              </button>
              <div className="lane-if">If {CO.buyer} says: “{LANE_IF[lane]}”</div>
            </div>
          </div>
        ))}

        <svg className="edges" width={worldW} height={ROW_Y.amber + ROW} aria-hidden>
          {edges.map(([a, b]) => {
            const d = edgePath(a, b);
            return (
              <g key={`${a.key}>${b.key}`}>
                <path d={d} className="edge" />
                <path d={d} className={`edge-on${status(b) !== "idle" ? " on" : ""}`} pathLength={1} />
              </g>
            );
          })}
        </svg>

        {placed.map((p) => {
          const n = run.nodes[p.key];
          const c = chip(n, p.step, (run.tracks[p.track].contract ?? run.tracks[p.track].amendment ?? run.tracks.shared.contract)?.lines.length ?? 0);
          const I = ICON[p.step.kind];
          const into = edges.some(([, b]) => b === p), out = edges.filter(([a]) => a === p);
          const open = () => onView(view.kind === "node" && view.key === p.key ? back(p) : { kind: "node", key: p.key });
          return (
            <div key={p.key} className={`node n-${n.status}${focused === p ? " focused" : ""}`} style={{ transform: `translate(${p.x}px, ${p.y}px)` }}
              role="button" tabIndex={0} aria-label={`${p.step.title}: ${c?.label ?? "Not started"}`} aria-expanded={focused === p}
              onClick={open} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }}>
              {c && (
                <span key={`${n.status}-${c.label}`} className={`chip ${c.cls}`}>
                  {n.status === "running" ? <svg className="spin" viewBox="0 0 16 16" aria-hidden><circle cx="8" cy="8" r="6" /><path d="M8 2a6 6 0 0 1 6 6" /></svg>
                    : c.cls === "done" ? <IcCheck size={11} strokeWidth={2.2} /> : <i className="sq-dot" />}
                  {c.label}
                </span>
              )}
              {into && <i className={`port in${n.status !== "idle" ? " on" : ""}`} />}
              {out.length > 0 && <i className={`port out${out.some(([, b]) => status(b) !== "idle") ? " on" : ""}`} />}
              <span className="tc-icon"><I size={15} /></span>
              <span className="node-t">
                <span className="node-title">{p.step.title}</span>
                <span className="node-desc">{p.step.detail}</span>
              </span>
            </div>
          );
        })}

        {placed.map((p) => {
          const n = run.nodes[p.key];
          if (p === focused || (!n.evidence.length && !n.rule)) return null;
          return (
            <div key={p.key} className="cards" style={{ transform: `translate(${p.x}px, ${p.y + H + 22}px)` }}>
              {n.evidence.map((e) => <EvidenceCard key={e.id} e={e} onSource={onSource} />)}
              {n.rule && <RuleCard rule={n.rule} />}
            </div>
          );
        })}

        {focused && (
          <div key={focused.key} ref={detail} className="detail" style={{ transform: `translate(${focused.x}px, ${focused.y + H + 14}px)` }}>
            <StepDetail step={focused.step} node={run.nodes[focused.key]} run={run} track={focused.track} highlight={highlight} onSource={onSource}
              decide={decide} binding={binding} />
          </div>
        )}

        {active && (
          <Orb x={active.x - 8} y={active.y - 56} mood={moodFor(active, run.nodes[active.key])} coin={coinFor(run, active.track)}
            label={`The agent is on: ${active.step.title}`} />
        )}
      </div>
    </div>
  );
}
