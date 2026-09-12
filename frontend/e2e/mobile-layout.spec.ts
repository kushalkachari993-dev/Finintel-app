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

  test("makes the horizontal prompt rail discoverable", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText(/Swipe to explore more prompts/i)).toBeVisible();
    await expect(page.getByLabel("Suggested research prompts")).toBeVisible();
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

  test("keeps keyboard focus inside the account dialog and restores it", async ({ page }) => {
    await page.goto("/");

    const accountButton = page.locator(".nav-auth-button");
    await accountButton.click();

    const dialog = page.getByRole("dialog", { name: /Sign in to continue|Account details/i });
    await expect(dialog).toBeVisible();
    await expect(page.locator(".chat-main")).toHaveAttribute("inert", "");

    await dialog.evaluate((element) => {
      const focusable = Array.from(element.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )).filter((item) => item.getClientRects().length > 0);
      focusable.at(-1)?.focus();
    });
    await page.keyboard.press("Tab");
    await expect.poll(() => dialog.evaluate(
      (element) => element.contains(document.activeElement)
    )).toBe(true);

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(accountButton).toBeFocused();
  });

  test("keeps separate drafts for chat and report modes", async ({ page }) => {
    await page.goto("/");

    const composer = page.locator("#query");
    await composer.fill("Current price of HDFC Bank");
    await page.getByLabel("Work mode").getByRole("button", { name: /^Report$/ }).click();
    await expect(composer).toHaveValue("");

    await composer.fill("Generate an HDFC Bank report");
    await page.getByLabel("Work mode").getByRole("button", { name: /^Chat$/ }).click();
    await expect(composer).toHaveValue("Current price of HDFC Bank");
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
