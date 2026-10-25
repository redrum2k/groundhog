// Actual local UI commands and screenshots; no playback fixture or browser-side rule injection.
const { chromium, expect } = require("@playwright/test");
const fs = require("node:fs/promises");
const path = require("node:path");

async function main() {
  const phase = process.argv[2];
  const output = path.resolve(process.argv[3] ?? "");
  const allowed = path.resolve(__dirname, "../../.local/live-learning/evidence");
  if (!["owner", "approval", "inspect"].includes(phase) || !output.startsWith(allowed + path.sep))
    throw new Error("Usage: node scripts/live-learning-ui.cjs owner|approval|inspect PROJECT_EVIDENCE_DIR");
  const errors = [];
  const browser = await chromium.launch({headless:true, channel:process.env.PLAYWRIGHT_CHANNEL ?? "msedge"});
  const page = await browser.newPage({viewport:{width:1440,height:1080}});
  page.on("pageerror", error => errors.push(error.message));
  const actions = [];
  try {
    await page.goto("http://127.0.0.1:3026/live", {waitUntil:"networkidle"});
    await page.getByRole("button", {name:/^(Source learning|Learning active)/}).click();
    const panel = page.getByRole("region", {name:"Persistent source learning"});
    await expect(panel).toBeVisible();
    await page.screenshot({path:path.join(output, `${phase}-before.png`)});
    if (phase === "owner") {
      for (const [family, column] of [["local-demo-partition-0","v_count"], ["local-demo-partition-1","p_adults"]]) {
        const choice = panel.getByLabel(`Count column for ${family}`);
        if (await choice.count() === 0) continue; // A completed resolution is never re-submitted.
        await choice.selectOption(column);
        await panel.getByLabel(`Owner explanation for ${family}`).fill(
          `Simulated DatumCo source owner: ${column} is the unique-adult count for ${family}; the other measure counts devices. This independently evidenced schema resolution covers later batches of this edition.`);
        const article = panel.locator("article").filter({has:page.getByText(family,{exact:true})});
        await article.getByRole("button", {name:"Answer as source owner"}).click();
        await expect(choice).toHaveCount(0, {timeout:15000});
        actions.push({action:"source_owner_resolved",family,column});
      }
      await expect(panel.getByRole("button", {name:"Answer as source owner"})).toHaveCount(0);
    } else if (phase === "approval") {
      await panel.getByRole("button", {name:"Propose a procedure"}).click();
      const qualify = panel.getByRole("button", {name:"Test on fresh cases"}).last();
      await expect(qualify).toBeEnabled();
      await qualify.click();
      await expect(panel.getByRole("heading",{name:"Passed on fresh cases"})).toBeVisible({timeout:45000});
      const approve = panel.getByRole("button",{name:"Approve as controller"}).last();
      await expect(approve).toBeEnabled();
      await approve.click();
      const activate = panel.getByRole("button",{name:"Turn on as controller"}).last();
      await expect(activate).toBeEnabled();
      await activate.click();
      await expect(panel.getByText("A learned procedure is on")).toBeVisible({timeout:15000});
      actions.push({action:"controller_qualified_approved_and_activated"});
    } else {
      await expect(panel.getByText("A learned procedure is on")).toBeVisible();
      const successful = panel.locator("article").filter({hasText:"Reviews needed: 2 → 0."}).filter({hasText:"Same input, with and without learning"}).last();
      const compared = successful.getByRole("button", {name:"Open this order"});
      if (await compared.count()) {
        await compared.click();
        await successful.scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(output,"live-comparison.png")});
      }
      await panel.getByRole("heading",{name:"Activity"}).scrollIntoViewIfNeeded();
      actions.push({action:"inspected_persisted_live_events"});
    }
    await page.screenshot({path:path.join(output,`${phase}-after.png`)});
    const visibleText = await panel.innerText();
    await fs.writeFile(path.join(output,`${phase}-ui.json`),JSON.stringify({
      url:page.url(),phase,actions,errors,visibleText,at:new Date().toISOString(),
      origin:"actual_running_application_not_playback",
    },null,2));
    if(errors.length) throw new Error(errors.join("\n"));
    console.log(JSON.stringify({phase,actions,screenshots:output,errors},null,2));
  } catch (error) {
    await page.screenshot({path:path.join(output,`${phase}-failure.png`)});
    throw error;
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
