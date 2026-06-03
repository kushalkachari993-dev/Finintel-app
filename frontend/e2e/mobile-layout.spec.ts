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
    await expect(page.locator(".chat-sidebar")).toBeVisible();
    await expect(page.locator(".chat-main")).toBeVisible();

    const horizontalOverflow = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollWidth - root.clientWidth;
    });

    expect(horizontalOverflow).toBeLessThanOrEqual(1);
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
