import { test, expect } from "@playwright/test";

async function selectHoanKiem(page) {
  const response = page.waitForResponse((response) => response.url().includes("/api/predict?lat=21.0285&lon=105.8542"));
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  return (await response).json();
}

test.beforeEach(async ({ page }) => {
  // The application must be usable without depending on third-party tile/font availability.
  await page.route(/https:\/\/(.*\.)?(tile\.openstreetmap\.org|tiles\.stadiamaps\.com|fonts\.googleapis\.com|fonts\.gstatic\.com)\//, (route) => route.abort());
  await page.goto("/");
  await expect(page.getByText("Demo mode", { exact: true })).toBeVisible();
});

test("explore a neighbourhood and display the full simulated snapshot", async ({ page }) => {
  const prediction = await selectHoanKiem(page);
  await expect(page.locator(".download-value")).toContainText(prediction.download_mbps.toFixed(1));
  await expect(page.getByText("Illustrative range", { exact: true })).toBeVisible();
  await expect(page.locator(".nearest-row")).toHaveCount(3);
  await expect(page.locator(".quality-badge")).toContainText(prediction.quality_level);
  await page.getByText("Behind the estimate", { exact: true }).click();
  await expect(page.locator(".model-details")).toContainText("demo-v1");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("coordinate entry rejects points outside the actual city boundary", async ({ page }) => {
  const predictionRequests = [];
  page.on("request", (request) => { if (request.url().includes("/api/predict?")) predictionRequests.push(request.url()); });
  await page.getByRole("textbox", { name: "Latitude and longitude" }).fill("21.3089, 105.6049");
  await page.getByRole("button", { name: "Explore coordinates", exact: true }).click();
  await expect(page.locator(".error-panel")).toContainText("outside Hanoi");
  await expect(page.locator(".download-value")).toHaveCount(0);
  await expect(page.locator(".selected-tooltip")).toHaveCount(0);
  expect(predictionRequests).toHaveLength(0);
  await page.getByRole("textbox", { name: "Latitude and longitude" }).fill("not coordinates");
  await page.getByRole("button", { name: "Explore coordinates", exact: true }).click();
  await expect(page.locator(".map-notice")).toContainText("Enter latitude, longitude");
});

test("typing coordinates and opening controls do not redraw the map", async ({ page }) => {
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await expect(page.locator(".download-value")).toBeVisible();
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.evaluate(() => {
    window.mapRedrawCount = 0;
    const original = CanvasRenderingContext2D.prototype.arc;
    CanvasRenderingContext2D.prototype.arc = function (...args) {
      window.mapRedrawCount++;
      return original.apply(this, args);
    };
  });
  await page.getByRole("textbox", { name: "Latitude and longitude" }).pressSequentially("21.0285, 105.8542", { delay: 15 });
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  expect(await page.evaluate(() => window.mapRedrawCount)).toBe(0);
});

test("a stalled optional font stylesheet cannot block the explorer", async ({ page }) => {
  await page.route("https://fonts.googleapis.com/**", () => {});
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "Hoàn Kiếm", exact: true })).toBeEnabled();
  const prediction = await selectHoanKiem(page);
  await expect(page.locator(".download-value")).toContainText(prediction.download_mbps.toFixed(1));
});

test("location access outside Hanoi does not request a prediction or leave the city", async ({ page, context }) => {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 10.7769, longitude: 106.7009 });
  const predictionRequests = [];
  page.on("request", (request) => { if (request.url().includes("/api/predict?")) predictionRequests.push(request.url()); });
  const tilesBefore = await page.locator(".leaflet-tile").evaluateAll((tiles) => tiles.map((tile) => tile.src).sort());
  await page.getByRole("button", { name: "Use my location", exact: true }).click();
  await expect(page.locator(".error-panel")).toContainText("outside Hanoi");
  const tilesAfter = await page.locator(".leaflet-tile").evaluateAll((tiles) => tiles.map((tile) => tile.src).sort());
  expect(tilesAfter).toEqual(tilesBefore);
  expect(predictionRequests).toHaveLength(0);
});

test("zooming out stops at the Hanoi region", async ({ page }) => {
  const zoomOut = page.getByRole("button", { name: "Zoom out", exact: true });
  await zoomOut.click();
  await zoomOut.click();
  await expect(zoomOut).toBeDisabled();
  await page.getByRole("button", { name: "Return to central Hanoi", exact: true }).click();
  await expect(zoomOut).toBeEnabled();
});

test("map clicks, layer toggles and project information work", async ({ page }) => {
  const map = page.locator(".leaflet-container");
  const box = await map.boundingBox();
  await map.click({ position: { x: box.width / 2, y: box.height / 2 } });
  await expect(page.locator(".result-card")).toBeVisible();
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  const towers = page.getByRole("checkbox", { name: "Tower locations", exact: true });
  await expect(towers).not.toBeChecked();
  await towers.check();
  await expect(towers).toBeChecked();
  await towers.uncheck();
  await expect(towers).not.toBeChecked();
  await page.getByRole("checkbox", { name: "Hanoi boundary", exact: true }).uncheck();
  await page.getByRole("button", { name: "About this project", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("no measured confidence coverage");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("a quiet basemap and selected speed take priority over optional tower details", async ({ page }) => {
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  await expect(page.getByRole("radio", { name: "Signal focus", exact: true })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Tower locations", exact: true })).not.toBeChecked();
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  const prediction = await selectHoanKiem(page);
  await expect(page.locator(".selected-tooltip")).toContainText(`${prediction.download_mbps.toFixed(1)} Mbps`);
  await expect(page.locator(".selected-tooltip")).toContainText(`${prediction.quality_level} connection`);
  await expect(page.locator(".selected-tooltip")).toContainText("simulated");
  await expect(page.locator(".cluster-count")).toHaveCount(0);
  await expect(page.getByLabel("Download speed quality legend")).toBeVisible();
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  await page.getByRole("radio", { name: "Detailed streets", exact: true }).check();
  await expect(page.locator(".leaflet-tile").first()).toHaveAttribute("src", /tile\.openstreetmap\.org/);
  await page.getByRole("radio", { name: "Signal focus", exact: true }).check();
  await expect(page.locator(".leaflet-tile").first()).toHaveAttribute("src", /tiles\.stadiamaps\.com/);
});

test("dataset tower labels stay separate from simulated speed labels", async ({ page }) => {
  const health = await (await page.request.get("/api/health")).json();
  const prediction = await (await page.request.get("/api/predict?lat=21.0285&lon=105.8542")).json();
  const towers = [
    { tower_id: 9101, latitude: 21.029, longitude: 105.8542, source: "opencellid", distance_m: 56 },
    { tower_id: 9102, latitude: 21.03, longitude: 105.855, source: "osm", distance_m: 186 },
    { tower_id: 9103, latitude: 21.031, longitude: 105.856, source: "opencellid", distance_m: 335 },
  ];
  await page.route("**/api/health", (route) => route.fulfill({ json: { ...health, tower_count: 3, tower_data_source: "dataset" } }));
  await page.route("**/api/towers", (route) => route.fulfill({ json: towers }));
  await page.route("**/api/predict?*", (route) => route.fulfill({ json: { ...prediction, nearest_towers: towers } }));
  await page.reload();
  await expect(page.locator(".mode-banner")).toContainText("local tower dataset");
  await expect(page.locator(".sidebar-footer")).toContainText("3 cell locations");
  await selectHoanKiem(page);
  await expect(page.locator(".nearest-heading")).toContainText("Closest cell locations");
  await expect(page.locator(".nearest-row").first()).toContainText("9101 · OpenCelliD");
  await expect(page.locator(".nearest-row").nth(1)).toContainText("OSM mast");
  await expect(page.locator(".result-type")).toHaveText("SIMULATED");
  await expect(page.locator(".selected-tooltip")).toContainText("simulated");
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "Tower locations", exact: true })).not.toBeChecked();
  await expect(page.locator(".layers-popover")).toContainText("Cell locations");
});

test("a slower previous prediction cannot overwrite the latest selection", async ({ page }) => {
  await page.route("**/api/predict?*", async (route) => {
    if (route.request().url().includes("lat=21.0285")) await new Promise((resolve) => setTimeout(resolve, 450));
    await route.continue();
  });
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await page.getByRole("button", { name: "Cầu Giấy", exact: true }).click();
  await expect(page.locator(".result-location strong")).toHaveText("Cầu Giấy");
  await expect(page.locator(".coordinates")).toContainText("21.03620");
});

test("connection failure offers reconnection and recovers", async ({ page }) => {
  await page.route("**/api/health", (route) => route.abort());
  await page.reload();
  await expect(page.getByRole("button", { name: "Reconnect", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Hoàn Kiếm", exact: true })).toBeDisabled();
  await page.unroute("**/api/health");
  await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  await expect(page.getByRole("button", { name: "Hoàn Kiếm", exact: true })).toBeEnabled();
});
