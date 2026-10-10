import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const stillsDir = path.join(root, "stills-check");
import { mkdirSync } from "node:fs";
mkdirSync(stillsDir, { recursive: true });

// key times: every scene + mid-transition / internal cut points (v2 10-scene narrative)
const times = [
  // S1 phone rings
  0.0, 1.0, 2.0, 3.0, 3.4,
  // S2 hook ladder
  3.6, 5.0, 7.0, 10.5, 11.5, 14.0, 17.0,
  // S3 urgency + payment (cut at 21 by save)
  17.3, 18.5, 20.0, 20.9,
  // S4 the save
  21.3, 22.5, 24.0, 26.0, 28.5,
  // S5 memory handshake
  29.0, 31.5, 33.5, 36.0, 38.5,
  // S6 debrief bridge
  39.0, 41.0, 43.0, 44.3,
  // S7 guardian dashboard
  44.6, 45.5, 47.0, 49.0,
  // S8 bot verdict
  49.2, 50.0, 50.9, 51.5, 52.1,
  // S9 scam graph
  52.4, 53.5, 55.2,
  // S10 outro
  55.6, 56.5, 57.5, 59.5,
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto("file:///" + path.join(root, "video.html").replace(/\\/g, "/"));
await page.waitForFunction("window.__ready === true", null, { timeout: 30000 });

for (const t of times) {
  await page.evaluate((tt) => window.__seek(tt), t);
  await page.waitForTimeout(30); // one paint
  const name = `t${String(t).replace(".", "_")}.png`;
  await page.screenshot({ path: path.join(stillsDir, name) });
  console.log("captured", name);
}

await browser.close();
console.log("done", times.length, "stills ->", stillsDir);
