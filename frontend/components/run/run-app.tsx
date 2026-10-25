"use client";
import { useEffect, useMemo, useState } from "react";
import type { Step } from "../../lib/run/contract";
import { project, type FoldContext, type View } from "../../lib/run/fold";
import { CONTRACT_V1, MAIN, S, controllerContinuation, stamp, timeline, type Case, type Ending } from "../../lib/run/scenario";
import { LIVE_API, usePlayback, type Feed } from "../../lib/run/source";
import Canvas, { type CanvasView, type CNode } from "./canvas";
import { IcLogo, IcPause, IcPlay, IcReplay, IcSummit } from "./icons";
import Customer from "./customer";
import Panel from "./panel";

// Groundhog's run screen. The canvas only ever sees the fold of events so far, so recorded
// playback and the live poll are interchangeable feeds.

type Mode = "recorded" | "live";
const MAIN_IDS = new Set(MAIN.map((s) => s.id));
// One order is the demo; the escalation is act two. The other scenario cases stay in the code for the recorded fallback.
const DEMO: [Case, string][] = [["green", "The order"], ["amber", "Escalation"]];
// Until a live stream plans the steps, the landing wording follows the backend, not the recorded sample
const LIVE_DETAIL: Record<string, string> = { paid: "Authorized on acceptance", review: "Accept or dispute" };
const ctxFor = (lane: Case, ending: Ending, learned: boolean): FoldContext => ({ lane, ending, learned, contract: CONTRACT_V1 });

/** The whole recorded run for a case, with Human's approval when the ending needs them. */
function fullEvents(c: Case, ending: Ending, learned: boolean) {
  const { events } = timeline(c, ending, learned);
  if (c !== "amber" || ending !== "human" || learned) return events;
  const v = project(events, ctxFor(c, ending, learned));
  return [...events, ...stamp("amber", controllerContinuation("approve", { deliveryVersion: 1, evidenceVersion: Object.keys(v.evidence).length }), events.length)];
}
const laneSteps = (lane: Case, ending: Ending, learned: boolean): Step[] => {
  const v = project(fullEvents(lane, ending, learned), ctxFor(lane, ending, learned));
  return v.order.filter((id) => !MAIN_IDS.has(id)).map((id) => v.nodes[id].step);
};
const toNodes = (steps: Step[], row: number, lane?: Case): CNode[] =>
  steps.map((s, col) => ({ id: s.id, row, col, title: s.title, desc: s.detail, lane: lane === "shared" ? undefined : lane, keepChip: s.kind === "verdict" || s.kind === "grey" }));
const canvasView = (v: View): CanvasView => ({
  status: Object.fromEntries(Object.entries(v.nodes).map(([id, n]) => [id, n.status])),
  chip: Object.fromEntries(Object.entries(v.nodes).map(([id, n]) => [id, n.chip])),
  orb: { node: v.orb.step, mode: v.orb.mode }, coin: v.coin, loops: v.loops, cards: v.cards,
  source: (() => { const n = Object.values(v.nodes).find((n) => n.source && n.status !== "idle"); return n?.source ? { node: n.step.id, lines: n.source } : null; })(),
});

export default function RunApp() {
  const [tab, setTab] = useState<"run" | "customer">("run");
  const [run, setRun] = useState<Case>("green");
  const [zoom, setZoom] = useState(true);
  const [ending, setEnding] = useState<Ending>("human");
  const [learned, setLearned] = useState(false);
  const [mode, setMode] = useState<Mode>("recorded");
  useEffect(() => { fetch(`${LIVE_API}/health`, { cache: "no-store" }).then((r) => r.ok && setMode("live")).catch(() => {}); }, []);
  const [feed, setFeed] = useState<Feed>(() => ({ kind: "recorded", ...timeline("green", "human"), start: 0, autoplay: false, ctx: ctxFor("green", "human", false) }));
  const [panel, setPanel] = useState<{ id: string; auto: boolean } | null>(null);
  const playback = usePlayback(feed);
  const { view, status } = playback;

  // Entrances and camera moves start after the first frame, never on load
  useEffect(() => { const id = requestAnimationFrame(() => { document.documentElement.dataset.anim = ""; }); return () => { cancelAnimationFrame(id); delete document.documentElement.dataset.anim; }; }, []);

  const steps = useMemo(() => (run === "shared" ? MAIN : [...MAIN, ...laneSteps(run, ending, learned)]), [run, ending, learned]);
  const stepOf = (id: string) => view.nodes[id]?.step ?? steps.find((s) => s.id === id); // a live stream's own step wins over the recorded plan

  const nodes = useMemo<CNode[]>(() => {
    const planned = (s: Step) => view.nodes[s.id]?.step ?? (mode === "live" && LIVE_DETAIL[s.id] ? { ...s, detail: LIVE_DETAIL[s.id] } : s);
    const main = toNodes(MAIN.map(planned), 0);
    if (run === "shared") return main;
    // the detour exists only once a dispute opens; nothing is pre-drawn
    const streamed = view.order.filter((id) => !MAIN_IDS.has(id)).map((id) => view.nodes[id].step);
    return [...main, ...toNodes(streamed, 1, run)];
  }, [run, view, mode]);
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

  const [recenter, setRecenter] = useState(0);
  const follow = () => setRecenter((n) => n + 1);
  const start = (c: Case, opts: { learned?: boolean; ending?: Ending; mode?: Mode; autoplay?: boolean } = {}) => {
    const e = opts.ending ?? ending, l = opts.learned ?? false, m = opts.mode ?? mode;
    setRun(c); setZoom(true); setPanel({ id: MAIN[0].id, auto: true }); setLearned(l); setEnding(e); follow();
    const ctx = ctxFor(c, e, l);
    if (m === "live" && !l) setFeed({ kind: "live", api: LIVE_API, body: { case: c }, before: [], ctx: { ...ctx, narrated: true } });
    else setFeed({ kind: "recorded", ...timeline(c, e, l), start: 0, autoplay: opts.autoplay ?? true, ctx });
  };
  const onNode = (id: string) => { playback.pause(); setPanel({ id, auto: false }); };
  const replayLearned = () => start("amber", { learned: true, ending: "human", mode: "recorded" });

  const panelStep = panel ? stepOf(panel.id) : undefined;
  // The last panel stays mounted while it slides out, then Panel reports it gone
  const [shown, setShown] = useState(panelStep);
  if (panelStep && panelStep !== shown) setShown(panelStep);
  const offerLearned = run === "amber" && ending === "human" && !learned && done;
  const caption = zoom ? (view.caption || (status === "idle" ? (mode === "live" ? "Press Play live to start the order on the backend." : "Press play to run the recorded order.") : "")) : S.positioning;
  const bodyProps = { view, lane: run, ending, learned, done, live: playback.live, decide: playback.decide, onReplayLearned: replayLearned };

  return (
    <div className="shell">
      <header className="top">
        <div className="brand"><IcLogo className="logo" size={22} /><div><div className="wordmark">{S.us}</div><div className="seat">{S.seat}</div></div></div>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "run"} className={tab === "run" ? "on" : ""} onClick={() => setTab("run")}>Run</button>
          <button role="tab" aria-selected={tab === "customer"} className={tab === "customer" ? "on" : ""} onClick={() => setTab("customer")}>Customer view</button>
        </div>
        <div className="top-r">
          {zoom && !learned && (
            <div className="seg quiet" aria-label="Feed">
              <button className={mode === "recorded" ? "on" : ""} onClick={() => { setMode("recorded"); start(run, { mode: "recorded" }); }}>Recorded</button>
              <button className={mode === "live" ? "on" : ""} onClick={() => { setMode("live"); start(run, { mode: "live" }); }}>Live</button>
            </div>
          )}
          {/* who this order is for; "Customer" keeps it from reading as the signed-in account */}
          <div className="account">
            <span className="avatar" aria-hidden><IcSummit size={15} strokeWidth={1.6} /></span>
            <div><div className="account-n">{S.buyer}</div><div className="account-r">Customer</div></div>
          </div>
        </div>
      </header>

      <div className="tools">
        <div className="seg cases">
          {DEMO.map(([c, label]) => (
            <button key={c} className={zoom && run === c ? "on" : ""} onClick={() => start(c)}><i className={`dot d-${c}`} />{label}</button>
          ))}
        </div>
        <div className="spacer" />
        {playback.awaiting && tab === "run" && (
          <button className="btn solid" onClick={() => setTab("customer")}>{playback.awaiting === "approve" ? "Summit's turn: approve the contract" : "Summit's turn: accept or object"}</button>
        )}
        {status === "error" && <span className="tools-err" role="alert">{playback.error}</span>}
        {zoom && (
          <>
            {/* once the run is done, Replay is the only next step, so it becomes the primary */}
            <button className={`btn${done && !offerLearned ? " solid" : ""}`} onClick={() => start(run, { learned, ending })}><IcReplay size={14} strokeWidth={1.6} />Replay</button>
            {offerLearned ? (
              <button className="btn solid" onClick={replayLearned}><IcReplay size={14} strokeWidth={1.6} />Replay yoga with the new rule</button>
            ) : !done && (
              <button className="btn solid" disabled={waiting || (playback.live && status !== "idle")} onClick={() => { if (playing) playback.pause(); else if (status === "idle" && mode === "live") start(run); else { follow(); playback.play(); } }}>
                {playing ? <IcPause size={14} strokeWidth={1.8} /> : <IcPlay size={14} strokeWidth={1.8} />}{playing ? "Pause" : waiting ? `Waiting on ${S.controller}` : mode === "live" && status === "idle" ? "Play live" : "Play"}
              </button>
            )}
          </>
        )}
      </div>

      {tab === "run" ? (
        <main className="stage">
          <Canvas
            nodes={nodes} view={cv} focus={{ kind: "follow" }}
            panelOpen={!!panelStep} onNode={onNode} recenter={recenter}
            midRun={status === "playing" || status === "waiting"}
          />
          {/* the narration is not on screen (the cards and chips carry it); screen readers still hear it */}
          <p className="sr-only cap-text" aria-live="polite">{caption}</p>
          {shown && <Panel key={shown.id + (learned ? "L" : "")} step={shown} {...bodyProps} closing={!panelStep} onClose={() => setPanel(null)} onClosed={() => setShown(undefined)} />}
        </main>
      ) : (
        // a beat after Summit's move, long enough to see the receipt line land, the view goes back to the agent at work
        <Customer run={run} steps={steps} view={view} bodyProps={bodyProps} awaiting={playback.awaiting} buyer={playback.buyer} onMoved={() => { window.setTimeout(() => setTab("run"), 600); }} />
      )}
    </div>
  );
}
