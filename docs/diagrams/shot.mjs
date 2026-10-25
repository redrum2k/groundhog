// Render a diagram page to PNG at 2x:
//   node docs/diagrams/shot.mjs docs/diagrams/stack.html docs/diagrams/stack.png
// Uses the frontend's Playwright install (npm install in frontend/ first) and the installed Google Chrome.
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const { chromium } = await import(pathToFileURL(resolve(here, "../../frontend/node_modules/playwright/index.mjs")).href);
const [html, out] = process.argv.slice(2).map((p) => resolve(p));

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 2000, height: 1200 }, deviceScaleFactor: 2 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(pathToFileURL(html).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.evaluate(() => window.draw?.());
// the arrows are added to the SVG by draw(); give the page one frame to paint them
await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
await page.locator("#stage").screenshot({ path: out });
if (errors.length) console.log("page errors:", errors);
await browser.close();
console.log("wrote", out);
