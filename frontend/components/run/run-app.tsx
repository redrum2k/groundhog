"use client";
import { useEffect, useMemo, useState } from "react";
import type { LaneId, Step } from "../../lib/run/contract";
import { project, type FoldContext, type View } from "../../lib/run/fold";
import { CASE_NAME, CONTRACT_V1, ENDINGS, LANES, MAIN, S, controllerContinuation, stamp, timeline, type Case, type Ending } from "../../lib/run/scenario";
import { LIVE_API, usePlayback, type Feed } from "../../lib/run/source";
import LiveRun from "./live-run";
import Canvas, { type CanvasView, type CNode } from "./canvas";
import { IcLogo, IcPause, IcPlay, IcReplay } from "./icons";
import Panel, { PanelBody } from "./panel";

// Datum Co.'s run screen. The canvas only ever sees the fold of events so far, so recorded
// playback and the live poll are interchangeable feeds.

type Mode = "recorded" | "live";
const MAIN_IDS = new Set(MAIN.map((s) => s.id));
const ctxFor = (lane: Case, ending: Ending, learned: boolean): FoldContext => ({ lane, ending, learned, contract: CONTRACT_V1 });

/** The whole recorded run for a case, with Maya's approval when the ending needs her. */
function fullEvents(c: Case, ending: Ending, learned: boolean) {
  const { events } = timeline(c, ending, learned);
  if (c !== "amber" || ending !== "maya" || learned) return events;
  const v = project(events, ctxFor(c, ending, learned));
  return [...events, ...stamp("amber", controllerContinuation("approve", { deliveryVersion: 1, evidenceVersion: Object.keys(v.evidence).length }), events.length)];
}
const laneSteps = (lane: LaneId, ending: Ending, learned: boolean): Step[] => {
  const v = project(fullEvents(lane, ending, learned), ctxFor(lane, ending, learned));
  return v.order.filter((id) => !MAIN_IDS.has(id)).map((id) => v.nodes[id].step);
};
const toNodes = (steps: Step[], row: number, lane?: LaneId, prefix = ""): CNode[] =>
  steps.map((s, col) => ({ id: prefix + s.id, row, col, title: s.title, desc: s.detail, lane, keepChip: s.kind === "verdict" || s.kind === "grey" }));
const canvasView = (v: View, prefix = ""): CanvasView => ({
  status: Object.fromEntries(Object.entries(v.nodes).map(([id, n]) => [prefix + id, n.status])),
  chip: Object.fromEntries(Object.entries(v.nodes).map(([id, n]) => [prefix + id, n.chip])),
  orb: { node: v.orb.step, mode: v.orb.mode }, coin: v.coin, loops: v.loops, cards: v.cards.map((c) => ({ ...c, node: prefix + c.node })),
});

export default function RunApp() {
  const [recorded, setRecorded] = useState(false);
  return recorded ? <><button className="btn" onClick={()=>setRecorded(false)}>Live backend</button><RecordedRunApp/></> : <LiveRun recorded={()=>setRecorded(true)}/>;
}

export function RecordedRunApp() {
  const [tab, setTab] = useState<"run" | "customer">("run");
  const [run, setRun] = useState<Case>("shared");
  const [zoom, setZoom] = useState(true);
  const [ending, setEnding] = useState<Ending>("maya");
  const [learned, setLearned] = useState(false);
  const [mode, setMode] = useState<Mode>("recorded");
  const [feed, setFeed] = useState<Feed>(() => ({ kind: "recorded", ...timeline("shared", "maya"), autoplay: false, ctx: ctxFor("shared", "maya", false) }));
  const [panel, setPanel] = useState<{ id: string; auto: boolean } | null>(null);
  const playback = usePlayback(feed);
  const { view, status } = playback;

  // Entrances and camera moves start after the first frame, never on load
  useEffect(() => { const id = requestAnimationFrame(() => { document.documentElement.dataset.anim = ""; }); return () => { cancelAnimationFrame(id); delete document.documentElement.dataset.anim; }; }, []);

  const steps = useMemo(() => (run === "shared" ? MAIN : [...MAIN, ...laneSteps(run, ending, learned)]), [run, ending, learned]);
  const stepOf = (id: string) => steps.find((s) => s.id === id);
  const total = useMemo(() => fullEvents(run, ending, learned).filter((e) => e.type === "step_started").length, [run, ending, learned]);

  // All cases: every lane in its finished state on one quiet map
  const overview = useMemo(() => {
    if (zoom) return null;
    const shared = project(fullEvents("shared", ending, false), ctxFor("shared", ending, false));
    const lanes = LANES.map((l) => [l, project(fullEvents(l, ending, false), ctxFor(l, ending, false))] as const);
    const nodes: CNode[] = [...toNodes(MAIN, 0), ...lanes.flatMap(([l, v], i) => toNodes(v.order.filter((id) => !MAIN_IDS.has(id)).map((id) => v.nodes[id].step), i + 1, l, `${l}:`))];
    const cv = canvasView(shared);
    for (const [l, v] of lanes) { const lv = canvasView(v, `${l}:`); for (const id of v.order) if (!MAIN_IDS.has(id)) { cv.status[`${l}:${id}`] = lv.status[`${l}:${id}`]; cv.chip[`${l}:${id}`] = lv.chip[`${l}:${id}`]; } }
    return { nodes, view: { ...cv, orb: null, coin: null, loops: [], cards: [] } satisfies CanvasView };
  }, [zoom, ending]);

  const nodes = useMemo<CNode[]>(() => {
    const planned = (s: Step) => view.nodes[s.id]?.step ?? s;
    const main = toNodes(MAIN.map(planned), 0);
    if (run === "shared") return main;
    const streamed = view.order.filter((id) => !MAIN_IDS.has(id)).map((id) => view.nodes[id].step);
    return [...main, ...toNodes(streamed.length ? streamed : steps.filter((s) => !MAIN_IDS.has(s.id)), 1, run)];
  }, [run, steps, view]);
  const cv = useMemo(() => canvasView(view), [view]);
  const playing = status === "playing";
  const done = status === "done";
  const waiting = status === "waiting";

  // Following the orb: open the panel on steps worth reading, close it on the others
  useEffect(() => {
    if (!zoom || (status !== "playing" && status !== "waiting")) return;
    const s = stepOf(view.orb.step);
    // the rerun's Produce is watched from the canvas, like the preview; its panel is one click away
    const rerun = s?.kind === "produce" && (view.nodes.produce?.attempt ?? 1) > 1;
    if (s?.panel && !rerun) setPanel({ id: s.id, auto: true });
    else setPanel((p) => (p?.auto ? null : p));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.orb.step, status]);

  const start = (c: Case, opts: { learned?: boolean; ending?: Ending; mode?: Mode; autoplay?: boolean } = {}) => {
    const e = opts.ending ?? ending, l = opts.learned ?? false, m = opts.mode ?? mode;
    setRun(c); setZoom(true); setPanel(null); setLearned(l); setEnding(e);
    const ctx = ctxFor(c, e, l);
    if (m === "live" && !l) setFeed({ kind: "fixture", api: LIVE_API, body: { case: c }, before: [], ctx });
    else setFeed({ kind: "recorded", ...timeline(c, e, l), autoplay: opts.autoplay ?? true, ctx });
  };
  const toOverview = () => { setZoom(false); playback.pause(); setPanel(null); };
  const onNode = (id: string) => {
    if (!zoom) {
      // jump into that lane, finished, with the step open
      const [lane, stepId] = id.includes(":") ? (id.split(":") as [LaneId, string]) : ["shared" as const, id];
      setRun(lane); setZoom(true); setLearned(false);
      setFeed({ kind: "still", events: fullEvents(lane, ending, false), ctx: ctxFor(lane, ending, false) });
      setPanel({ id: stepId, auto: false });
      return;
    }
    playback.pause();
    setPanel({ id, auto: false });
  };
  const replayLearned = () => start("amber", { learned: true, ending: "maya", mode: "recorded" });

  const panelStep = panel ? stepOf(panel.id) : undefined;
  const caption = zoom ? (view.caption || (status === "idle" ? "Press play to run this case." : "")) : S.positioning;
  const bodyProps = { view, lane: run, ending, learned, done, live: playback.live, decide: playback.decide, onReplayLearned: replayLearned };

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <IcLogo className="logo" />
          <div>
            <div className="title">Order {S.orderNo} <span className="faint">· {S.buyer}</span></div>
            <div className="seatline">{S.seat} · {S.us}</div>
          </div>
        </div>
        <div className="seg tabs" role="tablist">
          <button role="tab" aria-selected={tab === "run"} className={tab === "run" ? "on" : ""} onClick={() => setTab("run")}>Run</button>
          <button role="tab" aria-selected={tab === "customer"} className={tab === "customer" ? "on" : ""} onClick={() => setTab("customer")}>Customer view</button>
        </div>
        <div className="top-r">
          {zoom && !learned && (
            <div className="seg" aria-label="Feed">
              <button className={mode === "recorded" ? "on" : ""} onClick={() => { setMode("recorded"); start(run, { mode: "recorded" }); }}>Recorded</button>
              <button className={mode === "live" ? "on" : ""} onClick={() => { setMode("live"); start(run, { mode: "live" }); }}>Legacy broker demo</button>
            </div>
          )}
          <span className="tag">{playback.live ? "Legacy broker demo · scripted parties · mock payments" : "Recorded illustration · synthetic data · simulated decisions"}</span>
        </div>
      </header>

      <div className="tools">
        <div className="seg cases">
          <button className={!zoom ? "on" : ""} onClick={toOverview}>All cases</button>
          {(["shared", ...LANES] as Case[]).map((c) => (
            <button key={c} className={zoom && run === c ? "on" : ""} onClick={() => start(c)}><i className={`dot d-${c}`} />{CASE_NAME[c]}</button>
          ))}
        </div>
        {(run === "amber" || !zoom) && (
          <div className="ending">
            <span className="faint">Grey area ending</span>
            <div className="seg">
              {ENDINGS.map(([e, label]) => <button key={e} className={ending === e ? "on" : ""} onClick={() => (zoom ? start("amber", { ending: e }) : setEnding(e))}>{label}</button>)}
            </div>
          </div>
        )}
        <div className="spacer" />
        {status === "error" && <span className="tools-err" role="alert">{playback.error}</span>}
        {zoom && (
          <>
            <button className="btn" onClick={() => start(run, { learned, ending })}><IcReplay size={14} strokeWidth={1.6} />Replay</button>
            {run === "amber" && ending === "maya" && !learned && done ? (
              <button className="btn solid" onClick={replayLearned}><IcReplay size={14} strokeWidth={1.6} />Replay yoga with the new rule</button>
            ) : (
              <button className="btn solid" disabled={done || waiting || playback.live} onClick={() => (playing ? playback.pause() : playback.play())}>
                {playing ? <IcPause size={14} strokeWidth={1.8} /> : <IcPlay size={14} strokeWidth={1.8} />}{playing ? "Pause" : done ? "Done" : waiting ? `Waiting on ${S.controller}` : "Play"}
              </button>
            )}
          </>
        )}
        {!zoom && <button className="btn solid" onClick={() => start("shared")}><IcPlay size={14} strokeWidth={1.8} />Run the order</button>}
      </div>

      {tab === "run" ? (
        <main className="stage">
          <Canvas
            nodes={zoom ? nodes : overview!.nodes} view={zoom ? cv : overview!.view}
            focus={zoom ? { kind: "follow" } : { kind: "overview" }}
            panelOpen={!!panelStep} onNode={onNode} quiet={!zoom}
            overlay={
              <div className={`caption${panelStep ? " shifted" : ""}`} aria-live="polite">
                {zoom && <span className="cap-step">{view.started}/{total}</span>}
                <span key={caption} className="cap-text">{caption}</span>
              </div>
            }
          />
          {panelStep && <Panel key={panelStep.id + (learned ? "L" : "")} step={panelStep} {...bodyProps} onClose={() => setPanel(null)} />}
        </main>
      ) : (
        <Customer run={zoom ? run : "shared"} steps={steps} view={view} bodyProps={bodyProps} />
      )}
    </div>
  );
}

/** What the buyer sees: the same step content, in order, for the selected case. */
function Customer({ run, steps, view, bodyProps }: { run: Case; steps: Step[]; view: View; bodyProps: Omit<Parameters<typeof PanelBody>[0], "step"> }) {
  const ids: Record<Case, string[]> = { shared: ["clarify", "produce", "review"], red: ["clarify", "review", "investigate"], green: ["clarify", "review", "investigate", "amend"], amber: ["clarify", "review", "investigate", "decide"] };
  const show = ids[run].filter((id) => run === "shared" || id === "clarify" || id === "review" || (view.nodes[id]?.status ?? "idle") !== "idle");
  return (
    <main className="customer">
      <div className="cust-col">
        <div className="cust-h">
          <div className="title">{S.buyerAgent} <span className="faint">↔ {S.us} {S.agent.toLowerCase()}</span></div>
          <div className="faint" style={{ fontSize: 13 }}>What the customer sees. Follows the selected case: <b className="ink">{CASE_NAME[run]}</b>.</div>
        </div>
        {show.map((id) => {
          const s = steps.find((x) => x.id === id);
          return s ? <section key={id} className="cust-sec"><div className="cust-step">{s.title}</div><PanelBody step={s} {...bodyProps} customer /></section> : null;
        })}
      </div>
    </main>
  );
}
