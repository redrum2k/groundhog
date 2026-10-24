import { cleanup, render } from "@testing-library/react";
import { animate } from "motion/react";
import { useRef } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { GuideProvider, OrbSlot, useOrbFlight } from "../components/run/guide";

vi.mock("motion/react", () => ({ animate: vi.fn(() => ({ stop: vi.fn() })) }));
afterEach(cleanup);

function DecisionGuide() {
  const root = useRef<HTMLDivElement>(null);
  const at = useOrbFlight(root, "decision");
  return <GuideProvider value={{ at, mood: {} }}><div ref={root}><OrbSlot name="home" /><OrbSlot name="decision" /></div></GuideProvider>;
}

it("flies from home after the initial decision destination mounts and cleans up on unmount", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(10, 10, 34, 34));
  const { unmount } = render(<DecisionGuide />);
  const destination = document.querySelector<HTMLElement>('[data-orb-slot="decision"] .cust-orb');
  expect(animate).toHaveBeenCalledOnce();
  expect(destination?.style.visibility).toBe("hidden");
  expect(document.querySelectorAll(".orb-flyer")).toHaveLength(1);
  unmount();
  expect(document.querySelector(".orb-flyer")).toBeNull();
});
