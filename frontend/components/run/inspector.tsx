"use client";
import { animate } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ContractLine, Evidence, ZipCount } from "../../lib/run/contract";
import Orb from "./orb";

// When Acme objects, the orb takes out a magnifier and reads the delivery through it, then flies to what
// settles the objection: the contract term it rests on, or the term the data fails (red, with the row).

export type Look = { term?: string; row?: string; failed: boolean };
export type Found = { row?: boolean; term?: boolean; done?: boolean }; // done: it has pointed long enough to be seen

// The contract term an evidence item speaks to: live ids carry it (cite-geography, fail-2-freshness), recorded ones are listed
const TERM: Record<string, string> = { "e-line5": "coverage", "e-94110": "coverage", "e-city": "city", "e-line2": "city", "e-fitness": "fitness", "e-claim": "fitness", "e-wellness": "fitness", "e-v2": "yoga" };
const termOf = (e: Evidence) => TERM[e.id] ?? e.id.match(/^(?:cite|fail-\d+|unknown-\d+)-(.+)$/)?.[1];

/** What the investigation points at once it has evidence. Red only where the data fails a term. */
export function lookFor(evidence: Evidence[], lines: ContractLine[], rows: ZipCount[]): Look | null {
  const known = (id?: string) => (id && lines.some((l) => l.id === id) ? id : undefined);
  const failedCheck = evidence.find((e) => /^(?:fail|unknown)-\d+-/.test(e.id));
  if (failedCheck) return { term: known(termOf(failedCheck)), failed: true };
  const cell = evidence.find((e) => "row" in e && e.row);
  if (cell && "row" in cell && !rows.some((r) => r.zip === cell.row)) return { row: cell.row, term: known(termOf(cell)), failed: true };
  const term = evidence.map((e) => known(termOf(e))).find(Boolean);
  return term ? { term, failed: false } : null;
}

const LENS = { x: 43, y: 41 }, R = 14.5, MAG = 1.7; // the glass's centre in the orb's box, its inner radius, how much it enlarges
const EASE_IN_OUT = [0.77, 0, 0.175, 1] as const;

/** The orb with its glass, in the objected delivery's card. It reads the rows, then shows what `look` found. */
export default function Inspector({ look, found, onFound }: { look: Look | null; found: Found; onFound: (stage: keyof Found) => void }) {
  const root = useRef<HTMLSpanElement>(null), view = useRef<HTMLSpanElement>(null);
  const pos = useRef({ x: 0, y: 0 }), read = useRef(false);
  const [holding, setHolding] = useState(false);
  const [flying, setFlying] = useState(false);
  const report = useRef(onFound);
  report.current = onFound;

  // the card's own grid, never the copy inside the glass (which sits earlier in the card)
  const grid = () => root.current?.closest(".decision")?.querySelector<HTMLElement>(":scope > .review-grid");
  // where the orb stands untransformed: its slot, so every aim is the target's distance from there
  const origin = () => { const el = root.current, slot = el?.parentElement?.getBoundingClientRect(); return el && slot ? { x: slot.left + el.offsetLeft, y: slot.top + el.offsetTop } : null; };
  const lens = () => {
    const g = grid()?.getBoundingClientRect(), o = origin();
    if (!g || !o || !view.current) return;
    const lx = o.x + pos.current.x + LENS.x - g.left, ly = o.y + pos.current.y + LENS.y - g.top;
    view.current.style.transform = `translate(${R - lx * MAG}px, ${R - ly * MAG}px) scale(${MAG})`;
  };
  const place = (x: number, y: number, rot = 0) => { pos.current = { x, y }; if (!root.current) return; root.current.style.transform = `translate(${x}px, ${y}px) rotate(${rot}deg)`; lens(); };
  const aim = (target: Element | null | undefined, inset: number) => {
    const o = origin();
    if (!target || !o) return null;
    // the first line of its text: centring on a wrapped term would put the glass over the gap between lines
    const text = document.createRange();
    text.selectNodeContents(target);
    const r = text.getClientRects()[0] ?? target.getBoundingClientRect();
    return { x: r.left + inset - o.x - LENS.x, y: r.top + r.height / 2 - o.y - LENS.y };
  };

  // The glass shows a copy of the card's data, refreshed whenever what it found changes the card
  useEffect(() => {
    const real = grid();
    if (!holding || !real || !view.current) return;
    const copy = real.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
    copy.style.width = `${real.offsetWidth}px`;
    view.current.replaceChildren(copy);
    const rows = real.querySelector(".sheet-rows"), copied = copy.querySelector(".sheet-rows");
    if (rows && copied) copied.scrollTop = rows.scrollTop;
    lens();
  }, [holding, found.row, found.term, look?.row]);

  // A layout effect, so leaving cancels the run in the same commit that removes the orb: no frame or timer lands after it is gone
  useLayoutEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let alive = true, cancel = () => {};
    const go = (to: { x: number; y: number } | null, ms: number, arc: boolean) => new Promise<void>((done) => {
      if (!to) return done();
      if (reduce) { place(to.x, to.y); return done(); }
      const f = { ...pos.current }, dx = to.x - f.x, d = Math.max(1, Math.hypot(dx, to.y - f.y));
      const mx = (f.x + to.x) / 2, my = Math.min(f.y, to.y) - (arc ? Math.min(70, d * 0.28) : 0); // a flight lifts off; reading along a column doesn't
      if (arc) setFlying(true);
      const run = animate(0, 1, { duration: ms / 1000, ease: EASE_IN_OUT, onUpdate: (p) => {
        const q = 1 - p;
        place(q * q * f.x + 2 * q * p * mx + p * p * to.x, q * q * f.y + 2 * q * p * my + p * p * to.y, arc ? Math.max(-12, Math.min(12, (dx / d) * 12)) * Math.sin(Math.PI * p) : 0);
      }, onComplete: () => { setFlying(false); done(); } });
      cancel = () => { run.stop(); setFlying(false); done(); };
    });
    const pause = (ms: number) => new Promise<void>((done) => { const t = setTimeout(done, reduce ? 0 : ms); cancel = () => { clearTimeout(t); done(); }; });

    (async () => {
      const rows = grid()?.querySelector<HTMLElement>(".sheet-rows");
      if (!read.current) {
        await pause(200); if (!alive) return;
        setHolding(true); // takes out the glass
        await pause(220); if (!alive) return;
        const trs = [...(rows?.querySelectorAll("tbody tr") ?? [])], bottom = rows?.getBoundingClientRect().bottom ?? Infinity;
        const shown = trs.filter((r) => r.getBoundingClientRect().bottom <= bottom);
        await go(aim(trs[0]?.querySelector(".mono"), 22), 700, true); if (!alive) return;
        await go(aim(shown.at(-1)?.querySelector(".mono"), 22), Math.max(800, shown.length * 150), false); if (!alive) return;
        read.current = true;
      }
      if (!look) return; // holds the glass where it stopped reading until the evidence lands
      if (look.row) {
        const tr = rows?.querySelector<HTMLElement>(`[data-zip="${look.row}"]`);
        if (tr && rows) rows.scrollTop = Math.max(0, tr.offsetTop - rows.clientHeight / 2);
        await go(aim(tr?.querySelector(".mono"), 22), 650, true); if (!alive) return;
        await pause(260); if (!alive) return; // a beat: it noticed
        report.current("row");
        await pause(650); if (!alive) return;
      }
      if (look.term) {
        await go(aim(grid()?.querySelector(`[data-id="${look.term}"] .todo-title`), 34), 650, true); if (!alive) return;
      }
      report.current("term");
      await pause(1100); if (!alive) return; // holds the point long enough to read
      report.current("done");
    })();
    return () => { alive = false; cancel(); };
  }, [look?.row, look?.term, look?.failed]); // primitives: `look` is a fresh object every render

  const happy = !!found.term && !!look && !look.failed;
  return (
    <span ref={root} className={`cust-orb det${holding ? " holding" : ""}${flying ? " flying" : ""}`}>
      <svg className="det-tool det-handle" width="70" height="70" viewBox="0 0 70 70" aria-hidden><path d="M25 24 32 31" /><circle cx="25.5" cy="24.5" r="3.2" /></svg>
      <Orb mode={happy ? "happy" : "float"} />
      <span className="det-tool loupe" aria-hidden><span className="loupe-view" ref={view} /></span>
    </span>
  );
}
