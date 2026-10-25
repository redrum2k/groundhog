# Architecture diagrams

Two diagrams for the Devpost page and the pitch, drawn in one plain style: white background, dashed groups, one plain line per box.

- `stack.png` shows what runs where: the customer, Groundhog (FastAPI server, order agent, Next.js UI, SQLite), Claude for clarifying and verifying, Base Sepolia escrow, and the live canvas.
- `harness.png` shows one order from request to cash, the dispute lane, and the improvement harness that runs between orders.

## Re-render

Each diagram is an HTML page (`stack.html`, `harness.html`) with absolutely positioned boxes.
`arrows.js` draws the connectors into an SVG overlay from the boxes' real positions, so every arrow is straight.
Edit the HTML, then render at 2x with the frontend's Playwright install and the installed Google Chrome:

```sh
node docs/diagrams/shot.mjs docs/diagrams/stack.html docs/diagrams/stack.png
node docs/diagrams/shot.mjs docs/diagrams/harness.html docs/diagrams/harness.png
```

`canvas.png` is the laptop screen on the stack diagram, a still of `/demo` partway through an order taken by `canvas-shot.mjs` against a running frontend.
Brand icons in `icons/` come from simpleicons.org.
The groundhog is the canvas orb from `frontend/components/run/orb.tsx` with its CSS fills inlined.
