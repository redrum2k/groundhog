import { useEffect, useMemo, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import Canvas from "./Canvas";
import Panel, { PanelBody } from "./Panel";
import { S } from "./scenario";
import {
  laneOf, emptyView, laneBase, laneFrames, nodes, sharedFrames,
  type Ending, type Frame, type Lane, type View,
} from "./timeline";

type Run = "shared" | Lane;

const LANE_TONE: Record<Lane, string> = {
  red: "Our fault",
  green: "We were right",
  amber: "Grey area",
};
const RUN_LABEL: Record<Run, string> = { shared: "No dispute", red: "Our fault", green: "We were right", amber: "Grey area" };
const ENDING_LABEL: Record<Ending, string> = { rules_no: "Rules: we're right", rules_yes: "Rules: they're right", human: `${S.controller} decides` };

const framesFor = (run: Run, ending: Ending, learned: boolean) => (run === "shared" ? sharedFrames() : laneFrames(run, ending, learned));
const startFor = (run: Run) => (run === "shared" ? emptyView() : laneBase());
function fold(start: View, frames: Frame[], step: number) {
  let v = start;
  for (let i = 0; i <= step && i < frames.length; i++) v = frames[i].patch(v);
  return v;
}

/** Overview: every lane in its finished state on one screen. */
function overview(ending: Ending): View {
  const shared = fold(emptyView(), sharedFrames(), 99);
  const lanes = (["red", "green", "amber"] as Lane[]).map((l) => fold(laneBase(), laneFrames(l, ending, false), 99));
  const laneOnly = (v: View) => Object.fromEntries(Object.entries(v.status).filter(([k]) => !k.startsWith("s")));
  const laneChips = (v: View) => Object.fromEntries(Object.entries(v.chip).filter(([k]) => !k.startsWith("s")));
  return {
    ...shared,
    status: Object.assign({ ...shared.status }, ...lanes.map(laneOnly)),
    chip: Object.assign({ ...shared.chip }, ...lanes.map(laneChips)),
    loops: [],
    cards: lanes.flatMap((v) => v.cards.map((c) => ({ ...c, id: c.node + c.id }))),
    orb: { node: "s0", mode: "float" },
    coin: null,
    caption: S.positioning,
  };
}

export default function App() {
  const [tab, setTab] = useState<"run" | "customer">("run");
  const [run, setRun] = useState<Run>("shared");
  const [zoom, setZoom] = useState(true);
  const [ending, setEnding] = useState<Ending>("human");
  const [learned, setLearned] = useState(false);
  const [step, setStep] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [panel, setPanel] = useState<{ id: string; auto: boolean } | null>(null);

  const frames = useMemo(() => framesFor(run, ending, learned), [run, ending, learned]);
  const graph = useMemo(() => nodes(ending, zoom && run === "amber" ? learned : false, zoom ? (run === "shared" ? "none" : run) : undefined), [ending, learned, run, zoom]);
  const view = useMemo(() => (zoom ? fold(startFor(run), frames, step) : overview(ending)), [zoom, run, frames, step, ending]);
  const cur = frames[step];
  const done = step >= frames.length - 1;
  const waiting = cur?.wait === "human";

  const advance = () => setStep((s) => {
    const n = Math.min(s + 1, frames.length - 1);
    const f = frames[n];
    if (f.panel !== undefined) setPanel(f.panel ? { id: f.panel, auto: true } : null);
    return n;
  });

  useEffect(() => {
    if (!zoom || !playing || done || waiting) return;
    const t = setTimeout(advance, step < 0 ? 500 : cur.hold);
    return () => clearTimeout(t);
  }, [zoom, playing, step, done, waiting, frames]);

  useEffect(() => { if (done) setPlaying(false); }, [done]);

  const start = (r: Run, opts: { learned?: boolean; ending?: Ending } = {}) => {
    setRun(r); setZoom(true); setStep(-1); setPanel(null); setPlaying(true);
    setLearned(opts.learned ?? false);
    if (opts.ending) setEnding(opts.ending);
  };
  const toOverview = () => { setZoom(false); setPlaying(false); setPanel(null); };

  const onNode = (id: string) => {
    if (!zoom) {
      // jump into that lane, finished, with the step open
      const r: Run = laneOf(id) ?? "shared";
      setRun(r); setZoom(true); setLearned(false); setPlaying(false);
      setStep(framesFor(r, ending, false).length - 1);
      setPanel({ id, auto: false });
      return;
    }
    setPlaying(false);
    setPanel({ id, auto: false });
  };

  const panelNode = panel ? graph.find((n) => n.id === panel.id) : undefined;
  const caption = view.caption || (zoom ? "Press play to run this case." : "");

  const bodyProps = {
    view, lane: run, ending, learned,
    onHuman: advance,
    onReplayLearned: () => start("amber", { learned: true, ending: "human" }),
  };

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden><svg viewBox="0 0 16 16" width="14" height="14"><rect x="2" y="2" width="5" height="5" rx="1" fill="currentColor" /><rect x="9" y="2" width="5" height="5" rx="1" fill="currentColor" opacity=".45" /><rect x="2" y="9" width="5" height="5" rx="1" fill="currentColor" opacity=".45" /><rect x="9" y="9" width="5" height="5" rx="1" fill="currentColor" /></svg></span>
          <div>
            <div className="title">Order #1042 <span className="faint">· {S.buyer}</span></div>
            <div className="seatline">{S.seat} · {S.us}</div>
          </div>
        </div>
        <div className="seg tabs" role="tablist">
          <button role="tab" aria-selected={tab === "run"} className={tab === "run" ? "on" : ""} onClick={() => setTab("run")}>Run</button>
          <button role="tab" aria-selected={tab === "customer"} className={tab === "customer" ? "on" : ""} onClick={() => setTab("customer")}>Customer view</button>
        </div>
        <div className="top-r">
          <span className="tag">Recorded run · sample data</span>
        </div>
      </header>

      <div className="tools">
        <div className="seg cases">
          <button className={!zoom ? "on" : ""} onClick={toOverview}>All cases</button>
          {(["shared", "red", "green", "amber"] as Run[]).map((r) => (
            <button key={r} className={zoom && run === r ? "on" : ""} onClick={() => start(r)}>
              <i className={`dot d-${r}`} />{RUN_LABEL[r]}
            </button>
          ))}
        </div>
        {(run === "amber" || !zoom) && (
          <div className="ending">
            <span className="faint">Grey area ending</span>
            <div className="seg">
              {(Object.keys(ENDING_LABEL) as Ending[]).map((e) => (
                <button key={e} className={ending === e ? "on" : ""} onClick={() => (zoom ? start("amber", { ending: e }) : setEnding(e))}>{ENDING_LABEL[e]}</button>
              ))}
            </div>
          </div>
        )}
        <div className="spacer" />
        {zoom && (
          <>
            <button className="btn" onClick={() => start(run, { learned: run === "amber" && learned, ending })}><RotateCcw size={14} strokeWidth={1.6} />Replay</button>
            {run === "amber" && ending === "human" && !learned && done ? (
              <button className="btn solid" onClick={bodyProps.onReplayLearned}><RotateCcw size={14} strokeWidth={1.6} />Replay yoga with the new rule</button>
            ) : <button className="btn solid" disabled={done || waiting} onClick={() => (step < 0 && !playing ? setPlaying(true) : setPlaying(!playing))}>
              {playing ? <Pause size={14} strokeWidth={1.8} /> : <Play size={14} strokeWidth={1.8} />}{playing ? "Pause" : done ? "Done" : waiting ? `Waiting on ${S.controller}` : "Play"}
            </button>}
          </>
        )}
        {!zoom && <button className="btn solid" onClick={() => start("shared")}><Play size={14} strokeWidth={1.8} />Run the order</button>}
      </div>

      {tab === "run" ? (
        <main className="stage">
          <Canvas
            nodes={graph} view={view} laneTone={LANE_TONE}
            focus={zoom ? { kind: "follow" } : { kind: "overview" }}
            panelOpen={!!panelNode} onNode={onNode} quiet={!zoom}
            overlay={
              <div className={`caption${panelNode ? " shifted" : ""}`} aria-live="polite">
                {zoom && <span className="cap-step">{Math.max(0, step + 1)}/{frames.length}</span>}
                <span key={caption} className="cap-text">{caption}</span>
              </div>
            }
          />
          {panelNode && (
            <Panel key={panelNode.id + (learned ? "L" : "")} node={panelNode} {...bodyProps} firstVisit={panel!.auto}
              onClose={() => setPanel(null)} />
          )}
        </main>
      ) : (
        <Customer run={zoom ? run : "shared"} graph={graph} bodyProps={bodyProps} view={view} />
      )}
    </div>
  );
}

function Customer({ run, graph, bodyProps, view }: { run: Run; graph: ReturnType<typeof nodes>; view: View; bodyProps: Omit<Parameters<typeof PanelBody>[0], "node" | "firstVisit"> }) {
  const ids: Record<Run, string[]> = {
    shared: ["s0", "s3", "s5"],
    red: ["s0", "s5", "rI"],
    green: ["s0", "s5", "gI", "gA"],
    amber: ["s0", "s5", "aI", "aX"],
  };
  const show = ids[run].filter((id) => run === "shared" || id === "s0" || id === "s5" || (view.status[id] ?? "idle") !== "idle");
  return (
    <main className="customer">
      <div className="cust-col">
        <div className="cust-h">
          <div className="title">{S.buyerAgent} <span className="faint">↔ {S.us} {S.agent.toLowerCase()}</span></div>
          <div className="faint" style={{ fontSize: 13 }}>What the customer sees. Follows the selected case: <b className="ink">{RUN_LABEL[run]}</b>.</div>
        </div>
        {show.map((id) => {
          const n = graph.find((x) => x.id === id)!;
          return (
            <section key={id} className="cust-sec">
              <div className="cust-step">{n.title}</div>
              <PanelBody node={n} {...bodyProps} firstVisit={false} customer />
            </section>
          );
        })}
      </div>
    </main>
  );
}
