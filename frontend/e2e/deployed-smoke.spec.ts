import { expect, test } from "@playwright/test";

const frontendUrl =
  process.env.E2E_FRONTEND_URL || "https://finintel-ai-frontend.onrender.com";
const backendUrl =
  process.env.E2E_BACKEND_URL || "https://finintel-ai-backend.onrender.com";

test.describe("deployed public smoke", () => {
  test("backend health exposes deployed agents", async ({ request }) => {
    const response = await request.get(`${backendUrl}/health`);

    expect(response.ok()).toBeTruthy();

    const body = await response.json();

    expect(body.status).toBe("ok");
    expect(body.agents).toContain("report_agent");
  });

  test("backend supports uptime monitor HEAD requests", async ({ request }) => {
    const health = await request.head(`${backendUrl}/health`);
    const root = await request.head(`${backendUrl}/`);

    expect(health.status()).toBe(200);
    expect(root.status()).toBe(200);
  });

  test("chat and report endpoints reject anonymous requests cleanly", async ({
    request,
  }) => {
    const chat = await request.post(`${backendUrl}/chat`, {
      data: { query: "What is ROE?" },
    });
    const report = await request.post(`${backendUrl}/report`, {
      data: { query: "Generate a report on TCS" },
    });

    expect(chat.status()).toBe(401);
    expect(report.status()).toBe(401);
    await expect(chat.json()).resolves.toMatchObject({
      success: false,
      error: "Invalid or missing API key.",
    });
    await expect(report.json()).resolves.toMatchObject({
      success: false,
      error: "Invalid or missing API key.",
    });
  });

  test("backend accepts CORS preflight from deployed frontend", async ({
    request,
  }) => {
    const response = await request.fetch(`${backendUrl}/chat/stream`, {
      method: "OPTIONS",
      headers: {
        Origin: frontendUrl,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
      },
    });

    expect(response.status()).toBe(200);
    expect(response.headers()["access-control-allow-origin"]).toBe(frontendUrl);
  });

  test("frontend renders core research UI", async ({ page }) => {
    await page.goto("/");

    await expect(page).toHaveTitle(/FinIntel AI/);
    await expect(
      page.getByRole("heading", {
        name: /How can I help with Indian markets today/i,
      })
    ).toBeVisible();
    await expect(
      page.getByLabel("Work mode").getByRole("button", { name: /^Chat$/ })
    ).toBeVisible();
    await expect(
      page.getByLabel("Work mode").getByRole("button", { name: /^Report$/ })
    ).toBeVisible();
    await expect(page.getByPlaceholder(/Ask about HDFC Bank/i)).toBeVisible();
  });

  test("report mode changes composer behavior", async ({ page }) => {
    await page.goto("/");

    await page.getByLabel("Work mode").getByRole("button", { name: /^Report$/ }).click();

    await expect(
      page.getByPlaceholder(/Enter companies or a theme/i)
    ).toBeVisible();
    await expect(
      page.locator("form").getByRole("button", { name: /Generate report/i })
    ).toBeVisible();
  });
});
