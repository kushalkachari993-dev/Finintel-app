import { expect, test, type Page } from "@playwright/test";
import { clerk } from "@clerk/testing/playwright";

type HistoryItem = {
  conversation_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  pinned: boolean;
};

const now = Math.floor(Date.now() / 1000);
const clerkTestUserEmail = process.env.E2E_CLERK_USER_EMAIL || "";
const clerkTestConfigured = Boolean(
  process.env.CLERK_PUBLISHABLE_KEY
  && process.env.CLERK_SECRET_KEY
  && clerkTestUserEmail
);
test.skip(!clerkTestConfigured, "Clerk E2E credentials are not configured.");
const historyItems: HistoryItem[] = Array.from({ length: 75 }, (_, index) => ({
  conversation_id: `conversation-${index + 1}`,
  title: index === 71 ? "Renewable energy watchlist" : `Research conversation ${index + 1}`,
  created_at: now - index * 3_600,
  updated_at: now - index * 3_600,
  pinned: index === 0,
}));

async function loadHistory(page: Page) {
  await page.route("**/chat/conversations?*", async (route) => {
    const requestUrl = new URL(route.request().url());
    const search = (requestUrl.searchParams.get("search") || "").toLowerCase();
    const offset = Number(requestUrl.searchParams.get("offset") || "0");
    const limit = Number(requestUrl.searchParams.get("limit") || "30");
    const matches = search
      ? historyItems.filter((item) => item.title.toLowerCase().includes(search))
      : historyItems;

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        conversations: matches.slice(offset, offset + limit),
        has_more: offset + limit < matches.length,
      }),
    });
  });

  await page.route("**/chat/conversations/*", async (route) => {
    if (["PATCH", "DELETE"].includes(route.request().method())) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      });
      return;
    }

    await route.fallback();
  });

  await page.goto("/");
  await clerk.signIn({
    page,
    emailAddress: clerkTestUserEmail,
  });
  await page.reload();
}

test("keeps a large history bounded, searchable, and manageable", async ({ page }, testInfo) => {
  const startedAt = Date.now();
  await loadHistory(page);
  await expect(page.getByPlaceholder("Search research")).toBeVisible();
  await expect(page.locator(".history-item")).toHaveCount(30);
  const initialRenderMs = Date.now() - startedAt;

  await page.getByRole("button", { name: "Load more" }).click();
  await expect(page.locator(".history-item")).toHaveCount(60);

  await page.getByPlaceholder("Search research").fill("renewable energy");
  await expect(page.getByText("Renewable energy watchlist")).toBeVisible();
  await expect(page.locator(".history-item")).toHaveCount(1);

  await page.getByPlaceholder("Search research").fill("");
  await expect(page.locator(".history-item")).toHaveCount(30);

  await page.getByLabel("Actions for Research conversation 2", { exact: true }).click();
  await page.getByRole("menuitem", { name: "Pin to top" }).click();
  const pinnedGroup = page.locator(".history-group").filter({
    has: page.locator(".history-group-label", { hasText: "Pinned" }),
  });
  await expect(pinnedGroup.getByText("Research conversation 2")).toBeVisible();

  await page.getByLabel("Actions for Research conversation 1", { exact: true }).click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  await page.getByLabel("Conversation title").fill("Quarterly banking review");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Quarterly banking review")).toBeVisible();

  await page.getByLabel("Actions for Quarterly banking review").click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("menuitem", { name: "Confirm delete" }).click();
  await expect(page.getByText("Quarterly banking review")).toHaveCount(0);

  await testInfo.attach("large-history-performance.json", {
    body: JSON.stringify({ totalAvailable: historyItems.length, initialRendered: 30, initialRenderMs }, null, 2),
    contentType: "application/json",
  });
  expect(initialRenderMs).toBeLessThan(3_000);
});

test.describe("mobile history", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("keeps organization controls usable inside the navigation drawer", async ({ page }) => {
    await loadHistory(page);
    await page.getByRole("button", { name: "Open research navigation" }).click();
    await expect(page.getByPlaceholder("Search research")).toBeVisible();
    await page.getByPlaceholder("Search research").fill("renewable energy");
    await expect(page.getByText("Renewable energy watchlist")).toBeVisible();

    const rootOverflow = await page.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(rootOverflow).toBeLessThanOrEqual(1);
  });
});
