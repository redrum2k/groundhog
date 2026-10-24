# Preview v2: the run canvas to mirror

Open `order-agent-run.html` in a browser. It's the design source of truth for layout, flow and motion.
`src/` is the working React code behind it (scripted timeline, no backend). `screens/` shows the key states.

Rules of the design:
- Normal path is 5 steps: Clarify the order → Paid upfront → Produce & check → Customer review → Captured.
- A dispute is a short detour below the path (2–3 steps), then the orb carries the job back up to
  Produce & check and walks Review → Captured again. No separate Recheck / Redeliver / Books steps.
  - Our fault: Investigate → They're right → back to Produce (free rerun)
  - We were right: Investigate → We're right → Amendment → back to Produce
  - Grey area: Investigate → Grey area → (Rules decide | Maya decides) → back to Produce
- Only the selected case is on screen. "All cases" is a quiet map (verdict chips only, no cards, no orb).
- Opens on "No dispute", paused. Camera scale ~1, follows the orb. Step details open in one right panel
  (interview + live checklist, sheet with highlighted rows, citations, Maya's review, books + margin).
- Evidence cards pop under the step only while the orb is there; rule cards stay.
- Files: timeline.ts (steps + frames), Canvas.tsx (layout, edges, camera, orb), Panel.tsx (step panels),
  App.tsx (case picker, runner), styles.css (tokens + all classes), scenario.ts (names, amounts, text).
