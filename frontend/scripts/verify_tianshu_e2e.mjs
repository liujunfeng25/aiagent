/**
 * 端到端验证天枢大屏：登录 → iframe 内「相机调试」→ 截图
 * 运行：cd aiagent/frontend && node scripts/verify_tianshu_e2e.mjs
 */
import { chromium } from "playwright";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const BASE = process.env.TIANSHU_E2E_BASE || "http://127.0.0.1:8000";
const OUT_PARENT =
  process.env.TIANSHU_E2E_SHOT_PARENT || "/tmp/tianshu-e2e-parent.png";
const OUT_FRAME =
  process.env.TIANSHU_E2E_SHOT_FRAME || "/tmp/tianshu-e2e-frame.png";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  await page.goto(`${BASE}/tianshu`, {
    waitUntil: "domcontentloaded",
    timeout: 120000,
  });
  await sleep(2000);

  if (page.url().includes("/login")) {
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL(/tianshu/, { timeout: 60000 });
  }

  await sleep(2000);
  const iframeEl = page.locator("iframe.tianshu-iframe");
  await iframeEl.waitFor({ state: "visible", timeout: 30000 });

  const iframeHandle = await iframeEl.elementHandle({ timeout: 30000 });
  if (!iframeHandle) {
    throw new Error("无法取得 iframe elementHandle");
  }
  const frame = await iframeHandle.contentFrame();
  if (!frame) {
    throw new Error("无法取得 iframe contentFrame");
  }

  await sleep(22000);

  let camBtn = frame.getByRole("button", { name: "相机调试" });
  let n = await camBtn.count();
  if (n === 0) {
    camBtn = frame.locator("button.camera-debug-toggle");
    n = await camBtn.count();
  }
  if (n === 0) {
    camBtn = frame.getByText("相机调试", { exact: true });
    n = await camBtn.count();
  }
  const vis = n > 0 ? await camBtn.first().isVisible() : false;
  const bodyHasCam =
    (await frame
      .evaluate(() => document.body?.innerText?.includes("相机调试"))
      .catch(() => false)) === true;

  let clickedPanel = false;
  if (vis) {
    await camBtn.first().click();
    await sleep(800);
    const panel = frame.locator(".camera-debug-panel");
    clickedPanel =
      (await panel.count()) > 0 && (await panel.isVisible());
  }

  const wrapText = await frame
    .locator(".large-screen-wrap")
    .innerText()
    .catch(() => "");

  await page.screenshot({ path: OUT_PARENT, fullPage: true });
  await frame
    .locator(".large-screen")
    .screenshot({ path: OUT_FRAME })
    .catch(() => {});

  const result = {
    parentUrl: page.url(),
    cameraDebugCount: n,
    cameraDebugVisible: vis,
    bodyInnerTextHasCameraDebug: bodyHasCam,
    panelVisibleAfterClick: clickedPanel,
    wrapTextHasChaoyang: wrapText.includes("朝阳"),
    shots: { parent: OUT_PARENT, frame: OUT_FRAME },
  };
  console.log(JSON.stringify(result, null, 2));
  if (!vis) process.exitCode = 1;
} finally {
  await browser.close();
}
