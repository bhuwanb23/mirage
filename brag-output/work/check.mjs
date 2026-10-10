import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const stillsDir = path.join(root, "stills-check");
import { mkdirSync } from "node:fs";
mkdirSync(stillsDir, { recursive: true });

// key times: every scene + mid-transition / internal cut points
const times = [
  // S1 hook
  0.0, 1.0, 2.0, 3.0,
  // S2 reveal
  3.2, 4.0, 5.0, 6.5, 7.8,
  // S3 fire drill
  8.2, 9.5, 11.4, 11.7, 13.0, 14.1, 14.4, 15.5, 16.7, 17.0, 19.0, 20.8,
  // S4 guardian
  21.1, 22.0, 24.0, 25.0, 25.3, 27.0, 29.5, 29.8, 32.0, 34.5, 35.8,
  // S5 bot + verdict + graph
  36.0, 36.6, 37.5, 39.0, 39.8, 41.0, 43.1, 43.4, 45.0, 46.8,
  // S6 four layers
  47.0, 47.6, 48.5, 50.0, 53.0, 55.0,
  // S7 outro
  55.3, 56.0, 57.0, 58.5, 59.9,
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
