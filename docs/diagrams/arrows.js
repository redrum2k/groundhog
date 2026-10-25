// Draws connectors between absolutely positioned elements into the #wires SVG overlay.
// connect(from, to, { from: side, to: side, double, label, color, width, dash })
const STAGE = () => document.getElementById("stage").getBoundingClientRect();
function anchor(id, side, t = 0.5) {
  const r = document.getElementById(id).getBoundingClientRect(), s = STAGE();
  const x0 = r.left - s.left, y0 = r.top - s.top;
  if (side === "right") return [x0 + r.width, y0 + r.height * t];
  if (side === "left") return [x0, y0 + r.height * t];
  if (side === "top") return [x0 + r.width * t, y0];
  return [x0 + r.width * t, y0 + r.height];
}
const H = (s) => s === "left" || s === "right";
window.connect = function (a, b, o = {}) {
  const svg = document.getElementById("wires");
  const [x1, y1] = anchor(a, o.from, o.ft), [x2, y2] = anchor(b, o.to, o.tt);
  const color = o.color || "#111", w = o.width || 2;
  let d;
  if (o.elbow) {
    // orthogonal: out of the side, turn once, into the other side
    if (H(o.from) && H(o.to)) { const mx = o.mx ?? (x1 + x2) / 2; d = `M${x1},${y1} L${mx},${y1} L${mx},${y2} L${x2},${y2}`; }
    else if (!H(o.from) && !H(o.to)) { const my = o.my ?? (y1 + y2) / 2; d = `M${x1},${y1} L${x1},${my} L${x2},${my} L${x2},${y2}`; }
    else if (H(o.from)) d = `M${x1},${y1} L${x2},${y1} L${x2},${y2}`;
    else d = `M${x1},${y1} L${x1},${y2} L${x2},${y2}`;
  } else if (o.curve) {
    const k = o.curve;
    const c1 = H(o.from) ? [x1 + (o.from === "right" ? k : -k), y1] : [x1, y1 + (o.from === "bottom" ? k : -k)];
    const c2 = H(o.to) ? [x2 + (o.to === "left" ? -k : k), y2] : [x2, y2 + (o.to === "top" ? -k : k)];
    d = `M${x1},${y1} C${c1},${c2},${x2},${y2}`;
  } else d = `M${x1},${y1} L${x2},${y2}`;
  const id = `m${Math.random().toString(36).slice(2, 8)}`;
  const defs = svg.querySelector("defs");
  const head = (mid, rev) => `<marker id="${mid}" viewBox="0 0 10 10" refX="${rev ? 1 : 9}" refY="5" markerWidth="${o.head || 6}" markerHeight="${o.head || 6}" orient="auto"><path d="${rev ? "M10,0 L0,5 L10,10 z" : "M0,0 L10,5 L0,10 z"}" fill="${color}"/></marker>`;
  defs.insertAdjacentHTML("beforeend", head(id + "e", false) + (o.double ? head(id + "s", true) : ""));
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", color); p.setAttribute("stroke-width", w);
  if (o.dash) p.setAttribute("stroke-dasharray", o.dash);
  p.setAttribute("marker-end", `url(#${id}e)`); if (o.double) p.setAttribute("marker-start", `url(#${id}s)`);
  svg.appendChild(p);
  if (o.label) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    const mx = (x1 + x2) / 2 + (o.lx || 0), my = (y1 + y2) / 2 + (o.ly || 0);
    t.setAttribute("x", mx); t.setAttribute("y", my); t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "wire-label");
    const lines = o.label.split("\n");
    lines.forEach((l, i) => { const ts = document.createElementNS("http://www.w3.org/2000/svg", "tspan"); ts.setAttribute("x", mx); ts.setAttribute("dy", i ? "1.2em" : 0); ts.textContent = l; t.appendChild(ts); });
    const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    svg.appendChild(bg); svg.appendChild(t);
    const bb = t.getBBox(); bg.setAttribute("x", bb.x - 5); bg.setAttribute("y", bb.y - 3); bg.setAttribute("width", bb.width + 10); bg.setAttribute("height", bb.height + 6); bg.setAttribute("fill", o.labelBg || "#fff"); bg.setAttribute("rx", 3);
  }
};
