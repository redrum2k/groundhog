"use client";
import { useEffect, useRef, useState } from "react";
import type { Event, Job } from "../lib/jobflow.generated";
import { courierEvent } from "../lib/projection";
import { Badge, Button, Drawer } from "./ui";

function Creature() {
  return (
    <svg viewBox="0 0 80 64" width="54" height="44" aria-hidden="true">
      <path
        d="M22 42 17 57M49 42l8 15"
        stroke="currentColor"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M19 30C13 13 23 5 30 16c15-9 31 2 30 18 0 14-33 19-41-4Z"
        fill="#bcdb98"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="m26 15-4-9m15 8 3-8"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="43" cy="25" r="2.5" />
      <circle cx="53" cy="24" r="2.5" />
      <path d="m45 33 6 1" stroke="currentColor" strokeWidth="2" />
      <rect
        x="3"
        y="27"
        width="23"
        height="20"
        rx="3"
        fill="#f7e5b7"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path d="M14 28v7m-5 5h11" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
export function Courier({
  events,
  jobs = [],
  attemptLimit = 1,
}: {
  events: Event[];
  jobs?: Job[];
  attemptLimit?: number;
}) {
  const [replay, setReplay] = useState<Event[]>();
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const live = events.filter(courierEvent).at(-1);
  const current = replay ? replay[index] : live;
  const carriedJob = jobs.find((job) => job.id === current?.job_id);
  const attempt = carriedJob?.attempts?.find(
    (item) => item.id === current?.attempt_id,
  );
  const stage = attempt?.retry_from_stage ?? current?.payload?.retry_from_stage;
  const lastLive = useRef<string | undefined>(undefined);
  const [animateId, setAnimateId] = useState<string>();
  useEffect(() => {
    // Initial/reloaded history is shown statically; only newly received events move.
    if (lastLive.current && live?.id !== lastLive.current)
      setAnimateId(live?.id);
    lastLive.current = live?.id;
  }, [live?.id]);
  useEffect(() => {
    if (!playing || !replay) return;
    if (index >= replay.length - 1) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setIndex((i) => i + 1), 1600);
    return () => clearTimeout(timer);
  }, [playing, replay, index]);
  return (
    <section className="courier-bar" aria-label="Persisted correction activity">
      <div
        key={current?.id ?? "idle"}
        className={`creature ${current && (replay || animateId === current.id) ? "travel" : ""}`}
      >
        <Creature />
      </div>
      <div className="courier-copy">
        <strong>{replay ? "Read-only replay" : "Correction courier"}</strong>
        <p>
          {current
            ? `${current.type} · ${carriedJob?.label ?? current.job_id ?? "batch"} → ${String(stage ?? "recorded retry stage")}`
            : "Waiting for a recorded correction. No work is started here."}
        </p>
        {current && (
          <span className="small muted wrap">
            Event {current.id} ·{" "}
            {attempt
              ? `attempt ${attempt.number}/${attemptLimit} · ${attempt.status}`
              : `attempt ${current.attempt_id ?? "batch event"}`}
          </span>
        )}
      </div>
      <div className="row">
        {replay ? (
          <>
            <Badge>
              Playback {index + 1}/{replay.length}
            </Badge>
            <Button
              disabled={index >= replay.length - 1}
              onClick={() => setPlaying((p) => !p)}
            >
              {playing ? "Pause" : "Play"}
            </Button>
            <Button
              onClick={() => {
                setReplay(undefined);
                setPlaying(false);
              }}
            >
              Return to live
            </Button>
          </>
        ) : (
          <Button
            disabled={!events.some(courierEvent)}
            onClick={() => {
              setReplay(events.filter(courierEvent));
              setIndex(0);
              setPlaying(true);
            }}
          >
            Replay events
          </Button>
        )}
        <Drawer
          title="Event history"
          description="Persisted events only. Opening or replaying this history never executes an action."
          trigger={<Button variant="ghost">History</Button>}
        >
          <ol className="timeline">
            {events.map((event) => (
              <li key={event.id}>
                <strong>{event.type}</strong>
                <p className="small wrap">
                  #{event.sequence} · {event.timestamp}
                  <br />
                  {event.job_id ?? "Order"} · {event.id}
                  <br />
                  Causal ID: {event.causal_id}
                </p>
                <Badge>{event.mode ?? "SIMULATED"}</Badge>
                <pre>{JSON.stringify(event.payload, null, 2)}</pre>
              </li>
            ))}
          </ol>
        </Drawer>
      </div>
    </section>
  );
}
