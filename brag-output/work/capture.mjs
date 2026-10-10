import { chromium } from "playwright";
import path from "node:path";

const OUT = path.resolve("stills");
const BASE = "http://localhost:3000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await sleep(1200); // let landing animations settle

// 1. Landing hero
await page.screenshot({ path: path.join(OUT, "01-landing-hero.png") });

// 2. Landing "how it works" / features band — scroll to first section
await page.evaluate(() => window.scrollTo(0, window.innerHeight));
await sleep(700);
await page.screenshot({ path: path.join(OUT, "02-landing-band.png") });

// 3. Drill: setup
await page.goto(BASE + "/drill", { waitUntil: "networkidle" });
await sleep(600);
await page.fill("#drill-name", "Priya");
await page.screenshot({ path: path.join(OUT, "03-drill-setup.png") });

// 4. Drill: briefing
await page.click("text=Arm the drill");
await sleep(500);
await page.screenshot({ path: path.join(OUT, "04-drill-briefing.png") });

// 5. Drill: run
await page.click("button:has-text('Start')");
await sleep(600);
await page.screenshot({ path: path.join(OUT, "05-drill-run.png") });

// 6. Drill: debrief
await page.click("text=End & get debrief");
await sleep(600);
await page.screenshot({ path: path.join(OUT, "06-drill-debrief.png") });

// 7. Guardian: idle
await page.goto(BASE + "/guardian", { waitUntil: "networkidle" });
await sleep(600);
await page.screenshot({ path: path.join(OUT, "07-guardian-idle.png") });

// 8. Guardian: run full scam script, capture mid + late
await page.click("text=Start Listening");
await sleep(1500);
await page.click("text=Run full scam script");
await sleep(4000);
await page.screenshot({ path: path.join(OUT, "08-guardian-mid.png") });
await sleep(9000);
await page.screenshot({ path: path.join(OUT, "09-guardian-late.png") });

// stop call if button present
const stop = page.locator("button:has-text('Stop')");
if (await stop.count()) await stop.first().click().catch(() => {});
await sleep(800);

// 10. Graph
await page.goto(BASE + "/graph", { waitUntil: "networkidle" });
await sleep(1500);
await page.screenshot({ path: path.join(OUT, "10-graph.png") });

// 11. Dashboard
await page.goto(BASE + "/dashboard", { waitUntil: "networkidle" });
await sleep(1000);
await page.screenshot({ path: path.join(OUT, "11-dashboard.png") });

await browser.close();
console.log("done");
