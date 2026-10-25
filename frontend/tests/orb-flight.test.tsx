import { act, cleanup, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { GuideProvider, OrbSlot, useOrbFlight } from "../components/run/guide";
import { TUNNEL } from "../components/run/orb";

afterEach(() => { cleanup(); vi.useRealTimers(); });

function DecisionGuide() {
  const root = useRef<HTMLDivElement>(null);
  const at = useOrbFlight(root, "decision");
  return <GuideProvider value={{ at, mood: {} }}><div ref={root}><OrbSlot name="home" /><OrbSlot name="decision" /></div></GuideProvider>;
}

it("tunnels from home once the decision slot mounts: a copy ducks in where it stood, the real one waits under", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(10, 10, 34, 34));
  const { unmount } = render(<DecisionGuide />);
  const destination = document.querySelector<HTMLElement>('[data-orb-slot="decision"] .cust-orb');
  expect(destination?.classList.contains("tunnel-under")).toBe(true);
  const ghost = document.querySelector<HTMLElement>(".orb-flyer");
  expect(ghost?.classList.contains("tunnel-down")).toBe(true);
  expect(ghost?.style.transform).toBe("translate(10px, 10px)"); // where it stood, and it stays there
  unmount();
  expect(document.querySelector(".orb-flyer")).toBeNull();
});

it("climbs out at the new slot once the copy has gone in and the beat is over", () => {
  vi.useFakeTimers();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(10, 10, 34, 34));
  render(<DecisionGuide />);
  const destination = document.querySelector<HTMLElement>('[data-orb-slot="decision"] .cust-orb');
  act(() => { vi.advanceTimersByTime(TUNNEL.dive + TUNNEL.under - 1); });
  expect(destination?.classList.contains("tunnel-under")).toBe(true);
  act(() => { vi.advanceTimersByTime(1); });
  expect(destination?.classList.contains("tunnel-under")).toBe(false);
  expect(document.querySelector(".orb-flyer")).toBeNull();
});
