import { expect, test, type Page } from "@playwright/test";

const reportResult = {
  success: true,
  query: "Compare HDFC Bank and ICICI Bank as an investment report",
  answer_detail: "detailed",
  route: "REPORT",
  routing: {
    route: "REPORT",
    confidence: 0.96,
    reasoning: "Report mode selected.",
  },
  response: {
    success: true,
    error: null,
    data: {
      report_title: "HDFC Bank vs ICICI Bank",
      executive_summary: "Both banks are high-quality franchises with different valuation and growth trade-offs.",
      stock_overview: "A peer review focused on profitability, valuation, growth, and balance-sheet risk.",
      current_performance: "Both banks continue to deliver profitable growth.",
      risk_assessment: "Credit costs and deposit competition remain the primary watchpoints.",
      valuation_outlook: "Relative valuation should be assessed alongside sustainable return ratios.",
      research_view: "The preferred bank depends on valuation discipline and risk tolerance.",
      sector_context: "Indian private banks are competing for deposits while maintaining asset quality.",
      key_insights: [
        "HDFC Bank offers scale and a broad deposit franchise.",
        "ICICI Bank currently presents strong profitability and capital efficiency.",
      ],
      watchlist_triggers: ["Deposit growth", "Credit costs"],
      next_checks: ["Latest quarterly filing", "Management commentary"],
      source_quality: {
        source_count: 2,
        quality_view: "Primary filings and established market-data sources were used.",
      },
      companies: [
        {
          company_name: "HDFC Bank",
          ticker: "HDFCBANK.NS",
          business_snapshot: "Large diversified private-sector bank.",
          key_metrics: {
            current_price: "INR 1,720",
            market_cap: "INR 13.1T",
            pe_ratio: "19.4x",
            pb_ratio: "2.6x",
            roe: "14.8%",
            profit_margin: "24.1%",
            revenue_growth: "13.2%",
            debt_to_equity: "Not meaningful for banks",
          },
          financial_quality: "Stable asset quality and a broad funding base.",
          valuation_view: "Premium valuation reflects franchise quality.",
          growth_drivers: ["Deposit growth", "Cross-selling"],
          risks: ["Deposit competition"],
          analyst_takeaway: "Quality franchise with execution watchpoints.",
          sources: ["https://example.com/hdfc"],
        },
        {
          company_name: "ICICI Bank",
          ticker: "ICICIBANK.NS",
          business_snapshot: "Large private-sector bank with strong profitability.",
          key_metrics: {
            current_price: "INR 1,280",
            market_cap: "INR 9.0T",
            pe_ratio: "18.1x",
            pb_ratio: "3.1x",
            roe: "17.2%",
            profit_margin: "27.3%",
            revenue_growth: "15.5%",
            debt_to_equity: "Not meaningful for banks",
          },
          financial_quality: "Strong capital position and improving return ratios.",
          valuation_view: "Valuation is supported by profitability.",
          growth_drivers: ["Loan growth", "Operating leverage"],
          risks: ["Credit-cycle normalization"],
          analyst_takeaway: "Strong execution with valuation sensitivity.",
          sources: ["https://example.com/icici"],
        },
      ],
      sources_used: [
        "https://example.com/hdfc",
        "https://example.com/icici",
      ],
      confidence_score: 0.9,
      confidence_breakdown: {
        retrieval_score: 0.9,
        data_quality_score: 0.88,
      },
      guardrails: {
        applied: true,
        warnings: [],
        source_quality: { label: "Strong", source_count: 2 },
        data_quality: { label: "Good" },
      },
      disclaimer: "Educational research only.",
    },
  },
};

async function loadMockReport(page: Page) {
  await page.route("**/report/stream", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `event: final\ndata: ${JSON.stringify(reportResult)}\n\n`,
    });
  });

  await page.goto("/");
  await page.getByLabel("Work mode").getByRole("button", { name: /^Report$/ }).click();
  await page.getByPlaceholder(/Enter companies or a theme/i).fill(reportResult.query);
  await page.locator("form").getByRole("button", { name: /Generate report/i }).click();
  await expect(page.getByRole("heading", { name: "Financial comparison" })).toBeVisible();
}

test("renders a progressive report with a financial comparison matrix", async ({ page }) => {
  await loadMockReport(page);

  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader", { name: /HDFC Bank/ })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: /ICICI Bank/ })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "P/E Ratio" })).toBeVisible();

  const overview = page.locator("details").filter({ hasText: "Stock Overview" }).first();
  const context = page.locator("details").filter({ hasText: "Research Context" }).first();
  await expect(overview).toHaveAttribute("open", "");
  await expect(context).not.toHaveAttribute("open", "");

  const rootOverflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(rootOverflow).toBeLessThanOrEqual(1);

  await context.locator("summary").press("Enter");
  await expect(context).toHaveAttribute("open", "");
  await expect(context.getByText("Indian private banks are competing for deposits")).toBeVisible();
});

test("renders a qualitative peer decision table from the comparison contract", async ({ page }) => {
  const comparisonResult = {
    ...reportResult,
    query: "Compare HDFC Bank vs ICICI Bank",
    answer_detail: "detailed",
    route: "COMPARISON",
    response: {
      success: true,
      error: null,
      data: {
        comparison_type: "Peer Comparison",
        companies_compared: ["HDFC Bank", "ICICI Bank"],
        summary: "Both banks are established private-sector franchises.",
        winner_summary: "No universal winner; the choice depends on valuation and risk priorities.",
        comparative_analysis: [
          "HDFC Bank offers scale and a broad deposit franchise.",
          "ICICI Bank currently shows strong profitability and capital efficiency.",
        ],
        strengths: {
          "HDFC Bank": ["Scale", "Deposit franchise"],
          "ICICI Bank": ["Profitability", "Capital efficiency"],
        },
        risks: {
          "HDFC Bank": ["Deposit competition"],
          "ICICI Bank": ["Credit-cycle normalization"],
        },
        balanced_view: "Both require valuation discipline.",
        confidence_score: 0.86,
        sources_used: ["https://example.com/banks"],
        confidence_breakdown: { retrieval_score: 0.85 },
      },
    },
  };

  await page.route("**/chat/stream", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `event: final\ndata: ${JSON.stringify(comparisonResult)}\n\n`,
    });
  });

  await page.goto("/");
  await page.getByPlaceholder(/Ask about HDFC Bank/i).fill(comparisonResult.query);
  await page.locator("form").getByRole("button", { name: "Analyze" }).click();

  const peerTable = page.getByRole("region", {
    name: "Scrollable peer comparison table",
  }).getByRole("table");
  await expect(peerTable.getByRole("rowheader", { name: "HDFC Bank" })).toBeVisible();
  await expect(peerTable.getByRole("cell", { name: "Scale; Deposit franchise" })).toBeVisible();
  await expect(peerTable.getByRole("cell", { name: "Credit-cycle normalization" })).toBeVisible();
});

test.describe("mobile report", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("contains the comparison table without widening the page", async ({ page }) => {
    await loadMockReport(page);

    const tableRegion = page.getByRole("region", {
      name: "Scrollable financial comparison table",
    });
    const dimensions = await tableRegion.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      rootOverflow:
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }));

    expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth);
    expect(dimensions.rootOverflow).toBeLessThanOrEqual(1);
    await expect(page.locator(".chat-composer")).toBeInViewport();
  });
});
