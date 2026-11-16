import { test, expect } from "@playwright/test";

test("switches the selected model for the current location", async ({ page }) => {
  await page.route(/https:\/\/(.*\.)?(tile\.openstreetmap\.org|tiles\.stadiamaps\.com|fonts\.googleapis\.com|fonts\.gstatic\.com)\//, (route) => route.abort());
  await page.route("**/api/health", async (route) => {
    const response = await route.fetch();
    const status = await response.json();
    await route.fulfill({ json: { ...status, mode: "model", model_loaded: true } });
  });
  await page.route("**/api/models", (route) => route.fulfill({ json: { default: "knn", models: ["knn", "hybrid"] } }));
  await page.route("**/api/predict?*", async (route) => {
    const model = new URL(route.request().url()).searchParams.get("model");
    const response = await route.fetch();
    const prediction = await response.json();
    await route.fulfill({ json: { ...prediction, source: "model", model_name: model, area_download_mbps: model === "hybrid" ? 88 : 42 } });
  });
  await page.goto("/");
  const picker = page.getByLabel("Prediction model");
  await expect(picker).toHaveValue("knn");
  await page.getByRole("button", { name: "Hoàn Kiếm", exact: true }).click();
  await expect(page.locator(".download-value")).toContainText("42.0");
  await picker.selectOption("hybrid");
  await expect(page.locator(".download-value")).toContainText("88.0");
  await page.getByText("Behind the estimate", { exact: true }).click();
  await expect(page.locator(".model-details")).toContainText("Physics + XGBoost");
});
