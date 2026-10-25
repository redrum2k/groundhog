import { act, cleanup, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { GuideProvider, OrbSlot, useOrbFlight } from "../components/run/guide";
import { TUNNEL } from "../components/run/orb";

afterEach(() => { cleanup(); vi.useRealTimers(); });

function DecisionGuide() {
  const root = useRef<HTMLDivElement>(null);
  const at = useOrbFlight(root, "decision");
  // inside the customer view's scrolling pane, like the real one
  return <GuideProvider value={{ at, mood: {} }}><div className="customer"><div ref={root}><OrbSlot name="home" /><OrbSlot name="decision" /></div></div></GuideProvider>;
}

it("tunnels from home once the decision slot mounts: a copy ducks in where it stood, the real one waits under", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(10, 10, 34, 34));
  const { unmount } = render(<DecisionGuide />);
  const destination = document.querySelector<HTMLElement>('[data-orb-slot="decision"] .cust-orb');
  expect(destination?.classList.contains("tunnel-under")).toBe(true);
  const ghost = document.querySelector<HTMLElement>(".orb-flyer");
  expect(ghost?.classList.contains("tunnel-down")).toBe(true);
  expect(ghost?.parentElement?.className).toBe("customer"); // in the scrolling pane, so a scroll carries it off
  expect(ghost?.style.transform).toBe("translate(0px, 0px)"); // where it stood, relative to the pane (both measured at 10,10)
  unmount();
  expect(document.querySelector(".orb-flyer")).toBeNull();
});

it("climbs out at the new slot once the copy has gone in, the beat is over and the slot has stopped moving", () => {
  vi.useFakeTimers();
  const rect = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(10, 10, 34, 34));
  render(<DecisionGuide />);
  const destination = document.querySelector<HTMLElement>('[data-orb-slot="decision"] .cust-orb');
  act(() => { vi.advanceTimersByTime(TUNNEL.dive + TUNNEL.under); });
  expect(destination?.classList.contains("tunnel-under")).toBe(true); // one look is not yet still
  rect.mockReturnValue(new DOMRect(10, 300, 34, 34)); // the view is still scrolling the slot into place
  act(() => { vi.advanceTimersByTime(60); });
  expect(destination?.classList.contains("tunnel-under")).toBe(true);
  act(() => { vi.advanceTimersByTime(60); }); // same place twice: still
  expect(destination?.classList.contains("tunnel-under")).toBe(false);
  expect(document.querySelector(".orb-flyer")).toBeNull();
});
