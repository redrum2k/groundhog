// Ported from 21st.dev "Agent Todo List" (beui.dev/components/agents/todo-list).
// The structure, status icon and motion are the original's; Tailwind classes are swapped for our
// CSS tokens. The prompt did not include its three util files (ActionSwapRollText,
// AgentDisclosure, ease constants), so those are small stand-ins written here.
import { ChevronDown, ListTodo } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useCallback, useEffect, useId, useState } from "react";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;
const SPRING_SWAP = { type: "spring", stiffness: 520, damping: 34 } as const;
const SPRING_LAYOUT = { type: "spring", stiffness: 380, damping: 36 } as const;

export type TodoItemStatus = "pending" | "in-progress" | "completed" | "cancelled";
export interface TodoItem { id: string; title: ReactNode; status?: TodoItemStatus; progress?: number; detail?: ReactNode; tone?: "amber" }

function statusLabel(s: TodoItemStatus) {
  return s === "in-progress" ? "In progress" : s === "completed" ? "Completed" : s === "cancelled" ? "Cancelled" : "Pending";
}

// stand-in: rolls the number up when it changes
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

function TodoHeaderIcon({ complete }: { complete: boolean }) {
  const reduce = useReducedMotion() ?? false;
  return (
    <span aria-hidden="true" className="todo-hicon">
      <AnimatePresence initial={false} mode="popLayout">
        {complete ? (
          <motion.svg key="complete" viewBox="0 0 24 24" initial={reduce ? { opacity: 1 } : { opacity: 0, scale: 0.72 }}
            animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={reduce ? { duration: 0 } : SPRING_SWAP}
            style={{ position: "absolute", width: 22, height: 22, overflow: "visible", color: "var(--green)" }}>
            <circle cx="12" cy="12" r="9" fill="currentColor" />
            <motion.path d="M7.5 12.25 10.5 15.25 16.75 8.75" fill="none" stroke="white" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round"
              initial={reduce ? { pathLength: 1 } : { pathLength: 0 }} animate={{ pathLength: 1 }}
              transition={reduce ? { duration: 0 } : { duration: 0.24, ease: EASE_OUT }} />
          </motion.svg>
        ) : (
          <motion.span key="todo" initial={reduce ? { opacity: 1 } : { opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.72 }} transition={reduce ? { duration: 0 } : SPRING_SWAP}
            style={{ position: "absolute", display: "grid", placeItems: "center", color: "var(--ink-2)" }}>
            <ListTodo size={16} strokeWidth={1.5} />
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}

export function TodoStatusIcon({ status, progress, tone }: { status: TodoItemStatus; progress?: number; tone?: "amber" }) {
  const reduce = useReducedMotion() ?? false;
  const p = progress === undefined ? 0.68 : Math.min(100, Math.max(0, progress)) / 100;
  const color = status === "cancelled" ? "var(--red)" : status === "completed" ? "var(--green)"
    : status === "in-progress" ? (tone === "amber" ? "var(--amber)" : "var(--blue)") : "var(--ink-3)";
  return (
    <motion.svg aria-hidden="true" viewBox="0 0 24 24" initial={false} className="todo-sicon" style={{ color }}>
      <motion.circle cx="12" cy="12" r="9" fill="currentColor" stroke="currentColor" strokeWidth="1.5"
        strokeDasharray={status === "pending" ? "2 3" : undefined} strokeLinecap="round" initial={false}
        animate={{ fillOpacity: status === "completed" ? 0.08 : 0 }} transition={reduce ? { duration: 0 } : { duration: 0.18, ease: EASE_OUT }}
        style={{ opacity: status === "in-progress" ? 0.2 : 1 }} />
      <motion.circle cx="12" cy="12" r="9" pathLength="1" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" initial={false}
        animate={{
          pathLength: status === "in-progress" ? p : 0,
          opacity: status === "in-progress" ? 1 : 0,
          rotate: status === "in-progress" && progress === undefined && !reduce ? 360 : -90,
        }}
        transition={status === "in-progress" && progress === undefined && !reduce
          ? { rotate: { duration: 1.1, repeat: Infinity, ease: "linear" } } : reduce ? { duration: 0 } : SPRING_LAYOUT}
        style={{ transformOrigin: "12px 12px" }} />
      <motion.path d="M7.5 12.25 10.5 15.25 16.75 8.75" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        initial={false} animate={{ pathLength: status === "completed" ? 1 : 0, opacity: status === "completed" ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.24, ease: EASE_OUT }} />
      <motion.path d="M8.5 8.5 15.5 15.5M15.5 8.5 8.5 15.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
        initial={false} animate={{ pathLength: status === "cancelled" ? 1 : 0, opacity: status === "cancelled" ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.2, ease: EASE_OUT }} />
    </motion.svg>
  );
}

export default function TodoList({ items, title = "To-dos", defaultOpen = true }: { items: TodoItem[]; title?: ReactNode; defaultOpen?: boolean }) {
  const reduce = useReducedMotion() ?? false;
  const baseId = useId();
  const [open, setOpenState] = useState(defaultOpen);
  const completed = items.filter((i) => i.status === "completed").length;
  const allComplete = items.length > 0 && completed === items.length;
  const setOpen = useCallback((n: boolean) => setOpenState(n), []);
  useEffect(() => { if (!allComplete) setOpen(true); }, [allComplete, setOpen]);

  return (
    <section aria-label="Agent task list" className="todo">
      <button id={`${baseId}-t`} type="button" aria-expanded={open} aria-controls={`${baseId}-c`} onClick={() => setOpen(!open)} className="todo-head">
        <TodoHeaderIcon complete={allComplete} />
        <h3>{title}</h3>
        <span className={`todo-count${allComplete ? " all" : ""}`}>
          <span className="sr-only">{completed} of {items.length} tasks completed</span>
          <span aria-hidden="true" style={{ display: "inline-flex" }}><RollNumber value={completed} /><span>/</span><span>{items.length}</span></span>
        </span>
        <motion.span aria-hidden="true" animate={{ rotate: open ? 180 : 0 }} transition={reduce ? { duration: 0 } : SPRING_SWAP} className="todo-chev">
          <ChevronDown size={14} strokeWidth={1.5} />
        </motion.span>
      </button>
      {/* stand-in for AgentDisclosure: animated height */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div id={`${baseId}-c`} role="region" aria-labelledby={`${baseId}-t`} key="c"
            initial={reduce ? false : { height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={reduce ? { duration: 0 } : SPRING_LAYOUT} style={{ overflow: "hidden" }}>
            <ol aria-live="polite" className="todo-list">
              <AnimatePresence initial={false} mode="popLayout">
                {items.map((item) => {
                  const status = item.status ?? "pending";
                  return (
                    <motion.li layout="position" key={item.id} initial={reduce ? { opacity: 1 } : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -3 }}
                      transition={reduce ? { duration: 0 } : { opacity: { duration: 0.18, ease: EASE_OUT }, y: SPRING_LAYOUT, layout: SPRING_LAYOUT }}
                      className={`todo-item s-${status}`}>
                      <TodoStatusIcon status={status} progress={item.progress} tone={item.tone} />
                      <span className="sr-only">{statusLabel(status)}: </span>
                      <span className="todo-title">
                        <span style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
                          {item.title}
                          <motion.span aria-hidden="true" initial={false}
                            animate={{ scaleX: status === "completed" ? 1 : 0, opacity: status === "completed" ? 1 : 0 }}
                            transition={reduce ? { duration: 0 } : { duration: 0.28, ease: EASE_OUT, delay: 0.06 }} className="todo-strike" />
                        </span>
                      </span>
                      {item.detail ? <span className={`todo-detail${item.tone === "amber" && status === "in-progress" ? " amber" : ""}`}>{item.detail}</span> : null}
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
