import { expect, test } from "@playwright/test";

test("the home page answers", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
});

test("the health route names an adapter per port", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.status()).toBe(200);
  const body = (await response.json()) as { ok: boolean; ports: Record<string, string> };
  expect(body.ok).toBe(true);
  expect(Object.keys(body.ports)).toHaveLength(8);
});
