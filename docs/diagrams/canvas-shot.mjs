// A still of the /demo canvas mid-run, used as the laptop screen on the stack diagram:
//   node docs/diagrams/canvas-shot.mjs
// Needs the frontend dev server on :3000. With the backend up it presses "Play live", which creates a real demo order.
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const { chromium } = await import(pathToFileURL(resolve(here, "../../frontend/node_modules/playwright/index.mjs")).href);
const out = resolve(here, "canvas.png");

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
await page.goto("http://127.0.0.1:3000/demo", { waitUntil: "networkidle" });
const play = page.getByRole("button", { name: /^Play( live)?$/ });
const live = (await play.textContent())?.includes("live");
await play.click();
// the picture is of the order partway through, once the first acts are on the canvas
await page.waitForTimeout(live ? 14000 : 7000);
await page.screenshot({ path: out });
await browser.close();
console.log("wrote", out);
