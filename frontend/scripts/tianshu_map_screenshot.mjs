/**
 * 天枢地图页截图（headless）。在 frontend 目录执行：
 *   node scripts/tianshu_map_screenshot.mjs
 */
import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "../../..");
const outDir = join(repoRoot, ".playwright-mcp");
const outPath = join(outDir, "tianshu-map-east-west-check.png");

const url = process.env.TIANSHU_URL ?? "http://127.0.0.1:8000/tianshu/index.html#/gdMap";
const waitMs = Number(process.env.TIANSHU_WAIT_MS ?? 14000);

mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
try {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.locator("canvas").first().waitFor({ state: "visible", timeout: 90000 });
  await page.waitForTimeout(waitMs);
  try {
    await page.getByRole("button", { name: "初始视角" }).click({ timeout: 3000 });
    await page.waitForTimeout(2000);
  } catch {
    /* optional */
  }
  await page.screenshot({ path: outPath, type: "png" });
  console.log(outPath);
} finally {
  await browser.close();
}
