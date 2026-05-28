import { expect, test } from "@playwright/test";

const backendUrl =
  process.env.E2E_BACKEND_URL || "https://finintel-ai-backend.onrender.com";
const apiKey = process.env.E2E_BACKEND_API_KEY || "";
const runLiveAi = process.env.E2E_RUN_LIVE_AI === "true";

test.describe("deployed authenticated AI smoke", () => {
  test.skip(
    !runLiveAi || !apiKey,
    "Set E2E_RUN_LIVE_AI=true and E2E_BACKEND_API_KEY to run live provider checks."
  );

  test("brief educational chat returns a guarded response", async ({
    request,
  }) => {
    const response = await request.post(`${backendUrl}/chat`, {
      headers: {
        "X-API-Key": apiKey,
      },
      data: {
        query: "What is ROE?",
        answer_detail: "brief",
      },
      timeout: 60_000,
    });

    expect(response.ok()).toBeTruthy();

    const body = await response.json();

    expect(body.success).toBe(true);
    expect(body.route).toBe("EDUCATIONAL");
    expect(body.response.success).toBe(true);
    expect(body.response.data.simple_definition).toBeTruthy();
    expect(body.response.data.guardrails.applied).toBe(true);
  });

  test("report endpoint returns analyst report contract", async ({
    request,
  }) => {
    const response = await request.post(`${backendUrl}/report`, {
      headers: {
        "X-API-Key": apiKey,
      },
      data: {
        query: "Generate a fundamental report on TCS",
      },
      timeout: 90_000,
    });

    expect(response.ok()).toBeTruthy();

    const body = await response.json();

    expect(body.success).toBe(true);
    expect(body.route).toBe("REPORT");
    expect(body.response.success).toBe(true);
    expect(body.response.data.report_type).toBe("ANALYST_REPORT");
    expect(body.response.data.guardrails.applied).toBe(true);
  });
});
