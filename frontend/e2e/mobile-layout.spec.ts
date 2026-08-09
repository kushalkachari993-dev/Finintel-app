import { expect, test } from "@playwright/test";

test.describe("mobile layout", () => {
  test.use({
    viewport: { width: 390, height: 844 },
  });

  test("keeps the research app within the viewport", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", {
        name: /How can I help with Indian markets today/i,
      })
    ).toBeVisible();
    await expect(page.locator(".chat-sidebar")).toBeHidden();
    await expect(page.locator(".chat-main")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Open research navigation" })
    ).toBeVisible();
    await expect(page.locator(".chat-composer")).toBeInViewport();
    await expect(
      page.getByRole("button", { name: "Use prompt: What is ROE?" })
    ).toHaveCount(0);

    const composerHeight = await page
      .locator(".chat-composer")
      .evaluate((element) => element.getBoundingClientRect().height);

    const horizontalOverflow = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollWidth - root.clientWidth;
    });

    expect(horizontalOverflow).toBeLessThanOrEqual(1);
    expect(composerHeight).toBeLessThan(170);
  });

  test("opens and closes the research navigation drawer", async ({ page }) => {
    await page.goto("/");

    const sidebar = page.locator(".chat-sidebar");
    const menuButton = page.getByRole("button", {
      name: "Open research navigation",
    });

    await menuButton.click();

    await expect(sidebar).toBeVisible();
    await expect(page.locator(".mobile-nav-backdrop")).toBeVisible();
    await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
    await expect(menuButton).toHaveAttribute("aria-expanded", "true");

    const closeButton = page.getByRole("button", {
      name: "Close research navigation",
    }).last();

    await expect(closeButton).toBeFocused();
    await closeButton.click();

    await expect(sidebar).toBeHidden();
    await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");
    await expect(menuButton).toHaveAttribute("aria-expanded", "false");
    await expect(menuButton).toBeFocused();
  });

  test("keeps compact source cards readable", async ({ page }) => {
    await page.goto("/");

    await page.evaluate(() => {
      const thread = document.querySelector(".chat-thread");
      if (!thread) return;

      thread.innerHTML = `
        <section class="section source-section source-section-compact">
          <div class="section-heading-row">
            <h3>Verified sources</h3>
            <span>1 link</span>
          </div>
          <div class="source-grid">
            <a href="https://example.com/research/finintel-curated-finance-knowledge-base">
              <span class="source-index">1</span>
              <span>
                <strong>finintel curated finance knowledge base</strong>
                <small>research / finintel-curated-finance-knowledge-base</small>
              </span>
              <em>Open</em>
            </a>
          </div>
        </section>
      `;
    });

    const sourceTitle = page.locator(".source-grid strong");
    await expect(sourceTitle).toBeVisible();

    const sourceTitleWidth = await sourceTitle.evaluate(
      (element) => element.getBoundingClientRect().width
    );
    const horizontalOverflow = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollWidth - root.clientWidth;
    });

    expect(sourceTitleWidth).toBeGreaterThan(220);
    expect(horizontalOverflow).toBeLessThanOrEqual(1);
  });
});
