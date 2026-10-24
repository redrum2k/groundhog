"use client";
import { useMemo, useState } from "react";
import type { LaneId } from "../../lib/run/contract";
import { bindingFor, project } from "../../lib/run/fold";
import { CO, controllerContinuation, ENDINGS, LANE_NAME, LANES, stamp, timeline, type Ending } from "../../lib/run/scenario";
import { STUB_API, usePlayback, type Feed } from "../../lib/run/source";
import Canvas, { type View } from "./canvas";
import { IcPlay } from "./icons";
import { OrbMark } from "./orb";

// Datum Co.'s run screen. The canvas only ever sees the fold of events so far, so recorded
// playback and the live poll are interchangeable feeds.

type Focus = "all" | LaneId;
type Mode = "live" | "recorded";

export default function RunApp() {
  const [ending, setEnding] = useState<Ending>("controller");
  const [selected, setSelected] = useState<Focus>("all");
  const [mode, setMode] = useState<Mode>("live");
  const [view, setView] = useState<View>({ kind: "overview" });
  // At rest the canvas shows the whole run, with Maya's approval as the grey lane's default ending
  const still = useMemo<Feed>(() => {
    const { events } = timeline("all", ending);
    const rest = ending === "controller" ? stamp("amber", controllerContinuation("approve", bindingFor(project(events), "amber")), events.length) : [];
    return { kind: "still", events: [...events, ...rest] };
  }, [ending]);
  const [feed, setFeed] = useState<Feed | null>(null);
  const playback = usePlayback(feed ?? still);
  const { run, status, error, live } = playback;
  const playing = feed !== null && status !== "done";

  const show = (v: View) => {
    setView(v);
    if (v.kind === "overview") setSelected("all");
    if (v.kind === "lane") setSelected(v.lane);
  };
  const play = (as: Mode = mode) => {
    const { events, start } = timeline(selected, ending);
    setFeed(selected === "amber" && as === "live"
      ? { kind: "live", api: STUB_API, ending, before: events.slice(0, start) }
      : { kind: "recorded", events, start });
    setView({ kind: "follow" });
  };

  return (
    <div className="app">
      <header className="bar">
        <span className="brand"><OrbMark size={20} /> {CO.us}</span>
        <span className="vr" />
        <h1>{CO.title}</h1>
        <span className="faint">{CO.buyer} · ${CO.price}</span>
        <span className="spacer" />
        <span className="faint note">Sample run · synthetic data · mock payments</span>
      </header>

      <div className="stage">
        <Canvas run={run} view={view} onView={show} selected={selected} liveLane={live ? "amber" : undefined} decide={playback.decide} />

        <div className="dock">
          <div className="seg" role="group" aria-label="Show">
            <button aria-pressed={selected === "all"} onClick={() => show({ kind: "overview" })}>Whole run</button>
            {LANES.map((lane) => (
              <button key={lane} aria-pressed={selected === lane} onClick={() => show({ kind: "lane", lane })}>
                <i className={`sq ${lane}`} />{LANE_NAME[lane]}
              </button>
            ))}
          </div>
          {selected === "amber" && !playing && (
            <>
              <div className="seg" role="group" aria-label="Amber feed">
                <button aria-pressed={mode === "live"} onClick={() => setMode("live")}>Live</button>
                <button aria-pressed={mode === "recorded"} onClick={() => setMode("recorded")}>Recorded</button>
              </div>
              <div className="seg" role="group" aria-label="How the grey area ends">
                {ENDINGS.map(([e, label]) => <button key={e} aria-pressed={ending === e} onClick={() => setEnding(e)}>{label}</button>)}
              </div>
            </>
          )}
          {status === "error" && <span className="dock-err" role="alert">{error}</span>}
          {status === "waiting" && view.kind !== "follow" && <button className="btn" onClick={() => setView({ kind: "follow" })}>Open {CO.controller}'s review</button>}
          {playing && status !== "waiting" && view.kind !== "follow" && <button className="btn" onClick={() => setView({ kind: "follow" })}>Follow the agent</button>}
          {playing && live && <button className="btn" onClick={() => play("recorded")}>Play recorded ending</button>}
          {playing && !live && status !== "waiting" && <button className="btn" onClick={playback.skip}>Skip to end</button>}
          {!playing && (
            <button className="btn solid" onClick={() => play()}>
              <IcPlay size={12} /> Play {selected === "all" ? "the run" : selected === "amber" && mode === "live" ? "live" : "this lane"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
