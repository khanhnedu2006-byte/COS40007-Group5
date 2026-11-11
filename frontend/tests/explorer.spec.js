import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // The application must be usable without depending on third-party tile/font availability.
  await page.route(/https:\/\/(.*\.)?(tile\.openstreetmap\.org|tiles\.stadiamaps\.com|fonts\.googleapis\.com|fonts\.gstatic\.com)\//, (route) => route.abort());
  await page.goto("/");
  await expect(page.getByText("Demo mode", { exact: true })).toBeVisible();
});

test("explore a neighbourhood and display the regional simulated estimate", async ({ page }) => {
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await expect(page.locator(".download-value")).toContainText("Mbps");
  await expect(page.locator(".area-context")).toContainText("within 0.5 km");
  await expect(page.locator(".area-support")).toContainText("Simulated across");
  await expect(page.locator(".range-section, .secondary-metrics")).toHaveCount(0);
  await expect(page.locator(".nearest-row")).toHaveCount(3);
  await expect(page.locator(".quality-badge")).toContainText("Good");
  await page.getByText("Behind the estimate", { exact: true }).click();
  await expect(page.locator(".model-details")).toContainText("demo-regional-v1");
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
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await expect(page.locator(".download-value")).toContainText("Mbps");
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
  const towers = page.getByRole("checkbox", { name: /^(Demo towers|Tower locations)$/, exact: true });
  await expect(towers).not.toBeChecked();
  await towers.check();
  await expect(towers).toBeChecked();
  await towers.uncheck();
  await expect(towers).not.toBeChecked();
  await page.getByRole("checkbox", { name: "Hanoi boundary", exact: true }).uncheck();
  await page.getByRole("button", { name: "About this project", exact: true }).click();
  await expect(page.locator(".about-page")).toBeVisible();
  await page.getByRole("link", { name: "Back to signal explorer" }).click();
  await expect(page.locator(".about-page")).not.toBeVisible();
});

test("a quiet basemap and selected speed take priority over optional tower details", async ({ page }) => {
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  await expect(page.getByRole("radio", { name: "Signal focus", exact: true })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: /^(Demo towers|Tower locations)$/, exact: true })).not.toBeChecked();
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await expect(page.locator(".selected-tooltip")).toContainText("Mbps");
  await expect(page.locator(".selected-tooltip")).toContainText("0.5 km area");
  await expect(page.locator(".selected-tooltip")).toContainText("Good connection");
  await expect(page.locator(".selected-tooltip")).toContainText("simulated");
  await expect(page.locator(".cluster-count")).toHaveCount(0);
  await expect(page.getByLabel("Download speed quality legend")).toBeVisible();
  await page.getByRole("button", { name: "Map layers", exact: true }).click();
  await page.getByRole("radio", { name: "Detailed streets", exact: true }).check();
  await expect(page.locator(".leaflet-tile").first()).toHaveAttribute("src", /tile\.openstreetmap\.org/);
  await page.getByRole("radio", { name: "Signal focus", exact: true }).check();
  await expect(page.locator(".leaflet-tile").first()).toHaveAttribute("src", /tiles\.stadiamaps\.com/);
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

test("the regional circle is drawn at geographic scale", async ({ page }) => {
  await page.evaluate(() => {
    window.regionalRadii = [];
    const original = CanvasRenderingContext2D.prototype.arc;
    CanvasRenderingContext2D.prototype.arc = function (...args) {
      window.regionalRadii.push(args[2]);
      return original.apply(this, args);
    };
  });
  const response = page.waitForResponse((res) => res.url().includes('/api/predict?'));
  await page.getByRole('button', { name: 'Hoàn Kiếm', exact: true }).click();
  const result = await (await response).json();
  await expect(page.locator('.download-value')).toContainText(result.area_download_mbps.toFixed(1));
  await expect(page.locator('.area-context')).toContainText(`${(result.area_radius_m / 1000).toFixed(1)} km`);
  await expect.poll(() => page.evaluate(() => window.regionalRadii.some((r) => r > 30))).toBe(true);
});

test("model estimates identify sparse regional support and omit point metrics", async ({ page }) => {
  await page.route('**/api/health', (route) => route.fulfill({ json: {
    status: 'ok', ready: true, mode: 'model', model_loaded: true, model_version: 'regional-test', tower_count: 3,
  } }));
  await page.route('**/api/predict?*', (route) => route.fulfill({ json: {
    latitude: 21.0285, longitude: 105.8542, area_radius_m: 500,
    area_download_mbps: 123.4, area_quality_level: 'Good',
    area_points: 10, area_ookla_tiles: 1, area_grid_points: 9,
    nearest_towers: [], source: 'model', model_name: 'knn', model_version: 'regional-test',
  } }));
  await page.reload();
  await expect(page.getByText('Model connected', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Hoàn Kiếm', exact: true }).click();
  await expect(page.locator('.download-value')).toContainText('123.4');
  await expect(page.locator('.area-support')).toContainText('Sparse coverage: 9 grid points added');
  await expect(page.locator('.result-type')).toHaveText('ESTIMATE');
  await expect(page.locator('.range-section, .secondary-metrics')).toHaveCount(0);
  await page.getByText('Behind the estimate', { exact: true }).click();
  await expect(page.locator('.model-details')).toContainText('KNN');
});

test("the selected region stays centred when the map resizes", async ({ page }) => {
  await page.getByRole('button', { name: 'Hoàn Kiếm', exact: true }).click();
  await expect(page.locator('.download-value')).toBeVisible();
  const viewport = page.viewportSize();
  await page.setViewportSize({ width: viewport.width - 40, height: viewport.height });
  await expect.poll(async () => {
    const tooltip = await page.locator('.selected-tooltip').boundingBox();
    const map = await page.locator('.leaflet-container').boundingBox();
    return Math.abs((tooltip.x + tooltip.width / 2) - (map.x + map.width / 2));
  }).toBeLessThan(5);
});
