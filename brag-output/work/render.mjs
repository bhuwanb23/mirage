import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "frames");
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
});

await page.goto("file://" + path.join(__dirname, "video.html").replace(/\\/g, "/"));
await page.waitForFunction("window.__ready === true", { timeout: 15000 });

const FPS = 30;
const TOTAL = 1800;
const start = Date.now();

for (let i = 0; i < TOTAL; i++) {
  const t = i / FPS;
  await page.evaluate((tt) => window.__seek(tt), t);
  await page.screenshot({
    path: path.join(outDir, `f${String(i).padStart(4, "0")}.png`),
    type: "png",
  });
  if (i % 100 === 0) {
    const el = ((Date.now() - start) / 1000).toFixed(1);
    console.log(`frame ${i}/${TOTAL} t=${t.toFixed(2)} elapsed=${el}s`);
  }
}

await browser.close();
console.log(`done ${TOTAL} frames -> ${outDir} in ${((Date.now() - start) / 1000).toFixed(1)}s`);
