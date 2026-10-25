"use client";
import {useEffect, useRef, useState} from "react";
import {flushSync} from "react-dom";

type RunTab = "customer" | "run";

/** The old chat stays visible as a browser snapshot while the diagram arrives. */
export function useRunNavigation() {
  const [tab, setTab] = useState<RunTab>("customer");
  const target = useRef<RunTab>("customer");
  const keyboard = useRef(false);
  const revision = useRef(0);
  const transition = useRef<ViewTransition | null>(null);

  useEffect(() => () => {
    revision.current += 1;
    transition.current?.skipTransition();
    delete document.documentElement.dataset.runTransition;
  }, []);

  function navigate(next: RunTab, handoff = false) {
    if (target.current === next) return;
    target.current = next;
    const turn = ++revision.current;
    transition.current?.skipTransition();
    const commit = () => {
      if (turn !== revision.current) return;
      const moveFocus = !!document.activeElement?.closest(".customer, .stage");
      flushSync(() => setTab(next));
      if (moveFocus) document.querySelector<HTMLElement>(next === "run" ? ".live-shell .stage" : ".live-shell .customer")?.focus({preventScroll:true});
    };
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (keyboard.current || reduce || !document.startViewTransition) {
      delete document.documentElement.dataset.runTransition;
      commit();
      return;
    }
    document.documentElement.dataset.runTransition = handoff ? "handoff" : next;
    const move = document.startViewTransition(commit);
    transition.current = move;
    // A skipped/interrupted animation must not interrupt the accepted command.
    void move.ready.catch(() => {});
    void move.finished.catch(() => {}).finally(() => {
      if (turn === revision.current) {
        transition.current = null;
        delete document.documentElement.dataset.runTransition;
      }
    });
  }

  return {tab, navigate, interaction: {
    onPointerDownCapture: () => {keyboard.current = false;},
    onKeyDownCapture: () => {keyboard.current = true;},
  }};
}
