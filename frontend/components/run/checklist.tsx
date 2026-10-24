"use client";
// Ported from 21st.dev "Agent Todo List" (beui.dev/components/agents/todo-list): the structure,
// status icon and motion are the original's, Tailwind swapped for our CSS tokens. Here it shows
// the data contract as a checklist: lines appear as the interview drafts them and tick as checks pass.
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useId, useState } from "react";
import { IcChevron, IcList } from "./icons";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;
const SPRING_SWAP = { type: "spring", stiffness: 520, damping: 34 } as const;
const SPRING_LAYOUT = { type: "spring", stiffness: 380, damping: 36 } as const;

export type ItemStatus = "pending" | "in-progress" | "completed" | "cancelled";
export interface ChecklistItem { id: string; title: string; status: ItemStatus; detail?: string; mark?: "settles" | "fail" } // mark: what an inspection found on this line
const LABEL: Record<ItemStatus, string> = { "in-progress": "In progress", completed: "Completed", cancelled: "Failed", pending: "Pending" };

function RollNumber({ value }: { value: number }) {
  const reduce = useReducedMotion() ?? false;
  return (
    <span className="roll">
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span key={value} initial={reduce ? false : { y: "100%", opacity: 0 }} animate={{ y: 0, opacity: 1 }}
          exit={reduce ? { opacity: 0 } : { y: "-100%", opacity: 0 }} transition={reduce ? { duration: 0 } : SPRING_SWAP}>
          {value}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function StatusIcon({ status }: { status: ItemStatus }) {
  const reduce = useReducedMotion() ?? false;
  const color = status === "cancelled" ? "var(--red)" : status === "completed" ? "var(--green)" : status === "in-progress" ? "var(--blue)" : "var(--ink-3)";
  return (
    // plain svg root: motion keeps the style color it was mounted with, so the status color would never change
    <svg aria-hidden="true" viewBox="0 0 24 24" className="todo-sicon" style={{ color }}>
      <motion.circle cx="12" cy="12" r="9" fill="currentColor" stroke="currentColor" strokeWidth="1.5"
        strokeDasharray={status === "pending" ? "2 3" : undefined} strokeLinecap="round" initial={false}
        animate={{ fillOpacity: status === "completed" ? 0.08 : 0 }} transition={reduce ? { duration: 0 } : { duration: 0.18, ease: EASE_OUT }}
        style={{ opacity: status === "in-progress" ? 0.2 : 1 }} />
      {/* the arc's spin is CSS: Motion's mount animation never starts for an item that mounts already in progress */}
      <motion.circle cx="12" cy="12" r="9" pathLength="1" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
        className={status === "in-progress" ? "todo-arc spin" : "todo-arc"}
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: status === "in-progress" ? 0.68 : 0, opacity: status === "in-progress" ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : SPRING_LAYOUT} />
      <motion.path d="M7.5 12.25 10.5 15.25 16.75 8.75" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        initial={false} animate={{ pathLength: status === "completed" ? 1 : 0, opacity: status === "completed" ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.24, ease: EASE_OUT }} />
      <motion.path d="M8.5 8.5 15.5 15.5M15.5 8.5 8.5 15.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
        initial={false} animate={{ pathLength: status === "cancelled" ? 1 : 0, opacity: status === "cancelled" ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.2, ease: EASE_OUT }} />
    </svg>
  );
}

export default function TodoList({ items, title, defaultOpen = true }: { items: ChecklistItem[]; title: string; defaultOpen?: boolean }) {
  const reduce = useReducedMotion() ?? false;
  const baseId = useId();
  const [open, setOpen] = useState(defaultOpen);
  const completed = items.filter((i) => i.status === "completed").length;
  const all = items.length > 0 && completed === items.length;

  return (
    <section aria-label={title} className="todo">
      <button id={`${baseId}-t`} type="button" aria-expanded={open} aria-controls={`${baseId}-c`} onClick={() => setOpen(!open)} className="todo-head">
        <span aria-hidden className="todo-hicon" style={{ color: all ? "var(--green)" : "var(--ink-2)" }}><IcList size={15} /></span>
        <h3>{title}</h3>
        <span className={`todo-count${all ? " all" : ""}`}>
          <span className="sr-only">{completed} of {items.length} completed</span>
          <span aria-hidden style={{ display: "inline-flex" }}><RollNumber value={completed} /><span>/</span><span>{items.length}</span></span>
        </span>
        <motion.span aria-hidden animate={{ rotate: open ? 180 : 0 }} transition={reduce ? { duration: 0 } : SPRING_SWAP} className="todo-chev"><IcChevron size={13} /></motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div id={`${baseId}-c`} role="region" aria-labelledby={`${baseId}-t`} key="c"
            initial={reduce ? false : { height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={reduce ? { duration: 0 } : SPRING_LAYOUT} style={{ overflow: "hidden" }}>
            <ol aria-live="polite" className="todo-list">
              <AnimatePresence initial={false} mode="popLayout">
                {items.map((item) => (
                  <motion.li layout="position" key={item.id} initial={reduce ? { opacity: 1 } : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    exit={reduce ? { opacity: 0 } : { opacity: 0, y: -3 }}
                    transition={reduce ? { duration: 0 } : { opacity: { duration: 0.18, ease: EASE_OUT }, y: SPRING_LAYOUT, layout: SPRING_LAYOUT }}
                    data-id={item.id} className={`todo-item s-${item.status}${item.mark ? ` mark-${item.mark}` : ""}`}>
                    <StatusIcon status={item.status} />
                    <span className="sr-only">{LABEL[item.status]}: </span>
                    <span className="todo-title">{item.title}</span>
                    {item.detail && <span className="todo-detail">{item.detail}</span>}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
