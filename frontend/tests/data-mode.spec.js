import { test, expect } from "@playwright/test";

test("recorded estimates display data provenance without invented physics or confidence", async ({ page }) => {
  await page.route(/https:\/\/(.*\.)?(tile\.openstreetmap\.org|tiles\.stadiamaps\.com|fonts\.googleapis\.com|fonts\.gstatic\.com)\//, (route) => route.abort());
  await page.route("**/api/health", (route) => route.fulfill({ json: {
    ready: true, status: "ok", mode: "data", model_loaded: false,
    model_version: "ookla-spatial-v1-test", tower_count: 3, tower_data_source: "dataset",
    observation_count: 5212, data_period: "2026-3",
  } }));
  await page.route("**/api/predict?*", (route) => route.fulfill({ json: {
    area_download_mbps: 75, area_quality_level: "Fair", area_radius_m: 500, area_points: 5, area_ookla_tiles: 5, area_grid_points: 0,
    latitude: 21.0285, longitude: 105.8542, download_mbps: 75, download_low: 50, download_high: 150,
    upload_mbps: 12, latency_ms: 18, quality_level: "Fair", theory_mbps: null, local_effect_mbps: null,
    source: "data", model_version: "ookla-spatial-v1-test", interval_kind: "neighbour_spread", confidence_level: null,
    nearest_towers: [{ tower_id: "NEW-A", latitude: 21.03, longitude: 105.85, distance_m: 400, source: "opencellid" }],
    data_support: { tiles_used: 5, tests: 100, nearest_tile_distance_m: 120, latest_quarter: "2026-3" },
  } }));
  await page.goto("/");
  await expect(page.getByText("Data estimates", { exact: true })).toBeVisible();
  await expect(page.locator(".mode-banner")).toContainText("5,212 recorded Hanoi tiles through 2026-3");
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await expect(page.locator(".download-value")).toContainText("75.0");
  await expect(page.locator(".area-context")).toContainText("0.5 km");
  await expect(page.locator(".range-section")).toHaveCount(0);
  await page.getByText("Behind the estimate", { exact: true }).click();
  await expect(page.locator(".model-details")).toContainText("2026-3");
  await expect(page.locator(".model-details")).not.toContainText("Theoretical speed");
  await expect(page.locator(".model-details")).not.toContainText("Local adjustment");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
