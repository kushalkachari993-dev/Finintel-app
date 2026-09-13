import { useRef, useState, type ReactNode } from "react";
import type {
  AnswerDetail,
  ApiResult,
  Route,
  WorkMode,
} from "../types";

const ROUTE_LABELS: Record<string, string> = {
  PRICE_QUERY: "Price Check",
  EDUCATIONAL: "Learning",
  DISCOVERY: "Discovery",
  NEWS: "News",
  COMPARISON: "Comparison",
  FUNDAMENTAL: "Fundamentals",
  REPORT: "Analyst Report",
};

function asString(value: unknown, fallback = "") {
  if (value === null || value === undefined) {
    return fallback;
  }

  return String(value);
}

function asList(value: unknown) {
  const unique = (items: string[]) => Array.from(new Set(items));

  if (Array.isArray(value)) {
    return unique(value.map((item) => asString(item)).filter(Boolean));
  }

  if (typeof value === "string" && value.trim()) {
    return [value];
  }

  return [];
}

function asRecord(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asRecordList(value: unknown) {
  return Array.isArray(value)
    ? value
      .map((item) => asRecord(item))
      .filter((item) => Object.keys(item).length > 0)
    : [];
}

function routeLabel(route: Route) {
  return ROUTE_LABELS[route] || route.replaceAll("_", " ");
}

function formatPercent(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  const percent = numeric <= 1 ? numeric * 100 : numeric;
  return `${Math.round(percent)}%`;
}

function formatPrice(value: unknown, currency = "INR") {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return asString(value, "Unavailable");

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numeric);
}

function asFiniteNumber(value: unknown) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }

  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatSignedPrice(value: unknown, currency = "INR") {
  const numeric = asFiniteNumber(value);
  if (numeric === null) return "";

  const formatted = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Math.abs(numeric));

  return `${numeric >= 0 ? "+" : "−"}${formatted}`;
}

function formatSignedPercent(value: unknown) {
  const numeric = asFiniteNumber(value);
  if (numeric === null) return "";
  return `${numeric >= 0 ? "+" : "−"}${Math.abs(numeric).toFixed(2)}%`;
}

function formatCompactNumber(value: unknown) {
  const numeric = asFiniteNumber(value);
  if (numeric === null) return "Unavailable";

  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(numeric);
}

function formatQuoteTime(value: unknown) {
  const raw = asString(value);
  if (!raw) return "Not provided";

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

function providerLabel(value: unknown) {
  const provider = asString(value).toLowerCase();
  const labels: Record<string, string> = {
    yfinance: "Yahoo Finance",
    twelve_data: "Twelve Data",
    alpha_vantage: "Alpha Vantage",
    gemini_grounded_search: "Google-grounded search",
    tavily_web_search: "Trusted web search",
  };

  return labels[provider] || (provider ? provider.replaceAll("_", " ") : "Not provided");
}

function freshnessLabel(payload: Record<string, unknown>) {
  if (payload.price_date) {
    return `Closing price · ${asString(payload.price_date)}`;
  }

  const freshness = asString(payload.price_freshness).toLowerCase();
  if (freshness === "live_or_delayed") return "Live or delayed quote";
  if (freshness === "end_of_day") return "End-of-day quote";
  if (payload.is_market_open === true) return "Market open";
  if (payload.is_market_open === false) return "Latest available quote";
  return freshness ? freshness.replaceAll("_", " ") : "Freshness not provided";
}

function sourceDomain(source: string) {
  try {
    return new URL(source).hostname.replace(/^www\./, "");
  } catch {
    return source.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];
  }
}

function sourceLabel(source: string) {
  try {
    const url = new URL(source);
    const path = url.pathname
      .split("/")
      .filter(Boolean)
      .slice(-2)
      .join(" / ");

    return path || url.hostname.replace(/^www\./, "");
  } catch {
    return source.replace(/^https?:\/\/(www\.)?/, "");
  }
}

function sourceCountText(sources: unknown) {
  const count = asList(sources).length;

  if (!count) {
    return "No external source links were attached to this response.";
  }

  return `${count} source link${count === 1 ? "" : "s"} attached to this report.`;
}

function firstText(
  payload: Record<string, unknown>,
  keys: string[]
) {
  for (const key of keys) {
    const value = payload[key];

    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }

  return "";
}

function flattenedList(
  value: unknown
): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item): string[] => {
      if (typeof item === "string") return [item];
      if (item && typeof item === "object") {
        return Object.values(item).flatMap(flattenedList);
      }

      return [];
    });
  }

  if (value && typeof value === "object") {
    return Object.values(value).flatMap(flattenedList);
  }

  return typeof value === "string" && value.trim()
    ? [value]
    : [];
}

function reportMetrics(
  payload: Record<string, unknown>
) {
  const metricKeys: Record<string, string> = {
    current_price: "Current Price",
    pe_ratio: "P/E",
    market_cap: "Market Cap",
    sector: "Sector",
    sentiment: "Sentiment",
    recommendation: "Recommendation",
    confidence_score: "Confidence",
  };

  return Object.entries(metricKeys)
    .filter(([key]) => payload[key] !== null && payload[key] !== undefined && payload[key] !== "")
    .map(([key, label]) => ({
      label,
      value: key === "current_price"
        ? formatPrice(payload[key], asString(payload.currency, "INR"))
        : payload[key],
    }))
    .slice(0, 6);
}

function getConfidenceScore(
  payload: Record<string, unknown>
) {
  const payloadScore = Number(payload.confidence_score);
  if (Number.isFinite(payloadScore) && payloadScore > 0) return payloadScore;

  return 0;
}

function confidenceLabel(score: number) {
  if (score >= 0.85) return "Very high";
  if (score >= 0.7) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
}

type ResearchSignal = {
  label: string;
  detail: string;
  tone: "constructive" | "balanced" | "cautious" | "limited";
};

function getPayloadTitle(route: Route, payload: Record<string, unknown>) {
  if (route === "REPORT") return asString(payload.report_title) || "Analyst Report";
  if (route === "DISCOVERY") return "Discovery Ideas";
  if (route === "PRICE_QUERY") return asString(payload.company_name) || "Price Check";
  if (route === "EDUCATIONAL") return asString(payload.topic) || "Learning";
  if (route === "NEWS") return asString(payload.company_name) || "News Context";

  return (
    asString(payload.company_name) ||
    asString(payload.comparison_type) ||
    routeLabel(route)
  );
}

function getRouteSummary(route: Route, payload: Record<string, unknown>) {
  if (route === "REPORT") return payload.executive_summary;
  if (route === "PRICE_QUERY") return payload.message;
  if (route === "EDUCATIONAL") return payload.simple_definition;
  if (route === "DISCOVERY") return payload.summary;
  if (route === "NEWS") return payload.headline_summary;
  if (route === "COMPARISON") return payload.summary;
  return payload.overall_view || payload.business_overview;
}

function firstFlattenedText(...values: unknown[]) {
  for (const value of values) {
    const [first] = flattenedList(value);

    if (first) {
      return first;
    }
  }

  return "";
}

function conciseSnapshotText(value: unknown, fallback = "Not highlighted") {
  const text = asString(value, fallback).trim() || fallback;

  if (text.length <= 180) {
    return text;
  }

  return `${text.slice(0, 177).trim()}...`;
}

function getSnapshotView(route: Route, payload: Record<string, unknown>) {
  const directView = firstText(payload, [
    "recommendation",
    "investment_view",
    "overall_view",
    "balanced_view",
    "sentiment",
    "winner_summary",
    "valuation_outlook",
    "analyst_takeaway",
  ]);

  if (directView) {
    return directView;
  }

  if (route === "PRICE_QUERY") return "Price and market context";
  if (route === "EDUCATIONAL") return "Learning context";
  if (route === "DISCOVERY") return "Discovery screen";
  if (route === "NEWS") return "News impact context";
  if (route === "COMPARISON") return "Comparative research view";
  if (route === "REPORT") return "Analyst report view";

  return "Fundamental research view";
}

function getSnapshotReason(route: Route, payload: Record<string, unknown>) {
  return firstFlattenedText(
    getRouteSummary(route, payload),
    payload.executive_summary,
    payload.stock_overview,
    payload.summary,
    payload.message,
    payload.business_overview,
    payload.market_impact,
    payload.simple_definition,
    payload.routing_reason
  );
}

function getSnapshotRisk(payload: Record<string, unknown>) {
  const guardrails = asRecord(payload.guardrails);
  const companies = asList(payload.companies).map((company) => asRecord(company));
  const companyRisks = companies.flatMap((company) =>
    flattenedList(
      company.risks
      || company.risk_factors
      || company.financial_risks
      || company.risk_assessment
    )
  );

  return firstFlattenedText(
    payload.risk_assessment,
    payload.key_risks,
    payload.risk_factors,
    payload.financial_risks,
    payload.risks,
    payload.limitations,
    companyRisks,
    guardrails.warnings
  );
}

function getResearchSignal(
  route: Route,
  payload: Record<string, unknown>,
  score: number,
  sourceCount: number
): ResearchSignal {
  if (!sourceCount || (score > 0 && score < 0.5)) {
    return {
      label: "Evidence limited",
      detail: "Review source coverage before relying on this result.",
      tone: "limited",
    };
  }

  const signalText = [
    getSnapshotView(route, payload),
    getRouteSummary(route, payload),
    payload.valuation_outlook,
    payload.research_view,
    payload.winner_summary,
  ].map((value) => asString(value).toLowerCase()).join(" ");
  const cautiousTerms = [
    "bearish",
    "cautious",
    "negative",
    "overvalued",
    "deteriorating",
    "avoid",
    "material risk",
  ];
  const constructiveTerms = [
    "bullish",
    "constructive",
    "positive",
    "undervalued",
    "outperform",
    "favorable",
    "strong opportunity",
  ];

  if (cautiousTerms.some((term) => signalText.includes(term))) {
    return {
      label: "Cautious",
      detail: "The research view emphasizes downside or valuation risk.",
      tone: "cautious",
    };
  }

  if (constructiveTerms.some((term) => signalText.includes(term))) {
    return {
      label: "Constructive",
      detail: "The research view identifies favorable evidence.",
      tone: "constructive",
    };
  }

  return {
    label: route === "EDUCATIONAL" ? "Reference" : "Balanced",
    detail: route === "EDUCATIONAL"
      ? "Educational context, not a directional investment view."
      : "No single directional conclusion dominates the evidence.",
    tone: "balanced",
  };
}

function Metric({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined || value === "") return null;

  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{asString(value)}</strong>
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined || value === "") return null;

  return (
    <div className="stat-pill">
      <span>{label}</span>
      <strong>{asString(value)}</strong>
    </div>
  );
}

function Panel({
  title,
  children,
  tone = "neutral",
}: {
  title: string;
  children: unknown;
  tone?: "neutral" | "green" | "blue" | "red";
}) {
  if (!children || (Array.isArray(children) && children.length === 0)) {
    return null;
  }

  return (
    <section className={`panel panel-${tone}`}>
      <h3>{title}</h3>
      <div>{asString(children)}</div>
    </section>
  );
}

function ListPanel({
  title,
  items,
  tone = "blue",
}: {
  title: string;
  items: unknown;
  tone?: "blue" | "green" | "red";
}) {
  const list = asList(items);
  if (!list.length) return null;

  return (
    <section className="section">
      <h3>{title}</h3>
      <div className="list-stack">
        {list.map((item) => (
          <div className={`list-item list-${tone}`} key={item}>
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

function Sources({
  sources,
  compact = false,
}: {
  sources: unknown;
  compact?: boolean;
}) {
  const list = asList(sources);
  if (!list.length) return null;

  return (
    <section className={`section source-section ${compact ? "source-section-compact" : ""}`}>
      <div className="section-heading-row">
        <div>
          <small>Evidence register</small>
          <h3>{compact ? "Linked evidence" : "Research sources"}</h3>
        </div>
        <span>{list.length} source{list.length === 1 ? "" : "s"}</span>
      </div>
      <div className="source-grid">
        {list.map((source, index) => (
          <a
            href={source}
            target="_blank"
            rel="noreferrer"
            key={source}
            aria-label={`Open source ${index + 1}: ${sourceDomain(source)}`}
          >
            <span className="source-index">{index + 1}</span>
            <span>
              <strong>{sourceDomain(source)}</strong>
              <small>{sourceLabel(source)}</small>
            </span>
            <em>Open</em>
          </a>
        ))}
      </div>
    </section>
  );
}

function ConfidenceBreakdown({ breakdown }: { breakdown: unknown }) {
  const entries = Object.entries(asRecord(breakdown)).filter(
    ([, value]) => value !== null && value !== undefined && value !== ""
  );

  if (!entries.length) return null;

  return (
    <section className="section">
      <h3>Confidence Drivers</h3>
      <div className="breakdown-grid">
        {entries.map(([key, value]) => (
          <div className="breakdown-item" key={key}>
            <span>{key.replaceAll("_", " ")}</span>
            <strong>{asString(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function GuardrailNotice({ guardrails }: { guardrails: unknown }) {
  const payload = asRecord(guardrails);
  const warnings = asList(payload.warnings);
  const sourceQuality = asRecord(payload.source_quality);
  const dataQuality = asRecord(payload.data_quality);

  if (!payload.applied && !warnings.length) return null;

  return (
    <section className="guardrail-notice">
      <div>
        <small>Evidence protocol</small>
        <strong>Research quality checks</strong>
        <span>
          Sources: {asString(sourceQuality.label, "Not available")}
          {sourceQuality.source_count !== undefined
            ? ` (${sourceQuality.source_count})`
            : ""}
          {" | "}
          Data quality: {asString(dataQuality.label, "Not available")}
        </span>
      </div>
      {warnings.length > 0 && (
        <ul>
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AnalystReportTemplate({
  route,
  payload,
}: {
  route: Route;
  payload: Record<string, unknown>;
}) {
  const executiveSummary = asString(
    getRouteSummary(route, payload),
    firstText(payload, [
      "summary",
      "overall_view",
      "business_overview",
      "headline_summary",
      "simple_definition",
    ])
  );
  const researchView = firstText(payload, [
    "winner_summary",
    "market_impact",
    "overall_view",
    "valuation_commentary",
    "practical_interpretation",
    "balanced_view",
  ]);
  const risks = flattenedList(
    payload.risk_factors
    || payload.financial_risks
    || payload.risks
    || payload.limitations
  );
  const positives = flattenedList(
    payload.financial_strengths
    || payload.strengths
    || payload.key_points
    || payload.key_events
  );
  const metrics = reportMetrics(
    payload
  );

  if (!executiveSummary && !researchView && !risks.length && !positives.length && !metrics.length) {
    return null;
  }

  return (
    <ReportDisclosure
      number="A1"
      title="Analyst Report"
      description="Structured detailed view"
      defaultOpen
      className="analyst-template"
    >
      <div className="analyst-grid">
        {executiveSummary && (
          <article className="analyst-card analyst-card-wide">
            <span>01</span>
            <h4>Executive Summary</h4>
            <p>{executiveSummary}</p>
          </article>
        )}

        {metrics.length > 0 && (
          <article className="analyst-card">
            <span>02</span>
            <h4>Key Metrics & Evidence</h4>
            <div className="analyst-metrics">
              {metrics.map((metric) => (
                <div key={metric.label}>
                  <small>{metric.label}</small>
                  <strong>{asString(metric.value)}</strong>
                </div>
              ))}
            </div>
          </article>
        )}

        {researchView && (
          <article className="analyst-card">
            <span>03</span>
            <h4>Research View</h4>
            <p>{researchView}</p>
          </article>
        )}

        {positives.length > 0 && (
          <article className="analyst-card">
            <span>04</span>
            <h4>Positive Drivers</h4>
            <ul>
              {positives.slice(0, 4).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        )}

        {risks.length > 0 && (
          <article className="analyst-card">
            <span>05</span>
            <h4>Risks & Watchpoints</h4>
            <ul>
              {risks.slice(0, 4).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        )}

        <article className="analyst-card">
          <span>06</span>
          <h4>Next Checks</h4>
          <p>
            Validate latest filings, management commentary, sector trend,
            valuation context, and source freshness before making any decision.
          </p>
        </article>
      </div>
    </ReportDisclosure>
  );
}

function EmptyState({
  title,
  copy,
}: {
  title: string;
  copy: string;
}) {
  return (
    <section className="empty-state">
      <strong>{title}</strong>
      <span>{copy}</span>
    </section>
  );
}

function modeLabel(mode?: WorkMode) {
  return mode === "report" ? "Report" : "Chat";
}

function safeFileName(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 80)
    || "finintel-report";
}

async function exportElementToPdf(
  element: HTMLElement,
  title: string,
  reportOnly = false
) {
  const [
    { default: html2canvas },
    { default: jsPDF }
  ] = await Promise.all([
    import("html2canvas"),
    import("jspdf")
  ]);

  const disclosures = Array.from(element.querySelectorAll("details"));
  const disclosureStates = disclosures.map((details) => details.open);

  element.classList.add("pdf-exporting");
  element.classList.toggle("pdf-report-exporting", reportOnly);
  disclosures.forEach((details) => {
    details.open = true;
  });

  await document.fonts?.ready;
  await new Promise<void>((resolve) => requestAnimationFrame(() => {
    requestAnimationFrame(() => resolve());
  }));

  let canvas: HTMLCanvasElement;
  let breakPoints: number[] = [];

  try {
    const elementRect = element.getBoundingClientRect();
    const breakNodes = Array.from(element.querySelectorAll<HTMLElement>([
      ".report-cover",
      ".report-page > *",
      ".report-disclosure-content > *",
      ".report-company-card > *",
      ".report-three-grid > *",
      ".report-two-grid > *",
      ".source-section",
      ".disclaimer",
    ].join(",")));
    const breakRects = breakNodes
      .map((node) => node.getBoundingClientRect())
      .filter((rect) => rect.height > 0);
    const breakPointsCss = breakRects.flatMap((rect) => [
      rect.top - elementRect.top,
      rect.bottom - elementRect.top,
    ]).filter((point) => point > 0 && point <= elementRect.height + 1);

    canvas = await html2canvas(
      element,
      {
        backgroundColor: "#ffffff",
        scale: 1.5,
        useCORS: true
      }
    );

    const scaleY = canvas.height / Math.max(elementRect.height, 1);
    breakPoints = breakPointsCss.map((bottom) => Math.round(bottom * scaleY));
  } finally {
    disclosures.forEach((details, index) => {
      details.open = disclosureStates[index];
    });
    element.classList.remove("pdf-exporting");
    element.classList.remove("pdf-report-exporting");
  }
  const pdf = new jsPDF(
    "p",
    "mm",
    "a4"
  );
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 11;
  const footerHeight = 7;
  const imageWidth = pageWidth - margin * 2;
  const contentHeight = pageHeight - margin * 2 - footerHeight;
  const maxSliceHeight = Math.floor(
    canvas.width * contentHeight / imageWidth
  );
  const slices: Array<{ start: number; end: number }> = [];
  let sliceStart = 0;

  while (sliceStart < canvas.height) {
    const maximumEnd = Math.min(sliceStart + maxSliceHeight, canvas.height);
    const minimumEnd = sliceStart + maxSliceHeight * 0.28;
    const safeEnds = breakPoints.filter(
      (point) => point >= minimumEnd && point <= maximumEnd
    );
    let sliceEnd = safeEnds.length
      ? Math.max(...safeEnds)
      : maximumEnd;

    if (canvas.height - sliceEnd < maxSliceHeight * 0.08) {
      sliceEnd = canvas.height;
    }

    slices.push({ start: sliceStart, end: sliceEnd });
    sliceStart = sliceEnd;
  }

  slices.forEach(({ start, end }, index) => {
    if (index > 0) pdf.addPage();

    const sliceCanvas = document.createElement("canvas");
    sliceCanvas.width = canvas.width;
    sliceCanvas.height = end - start;
    const context = sliceCanvas.getContext("2d");

    if (!context) {
      throw new Error("Unable to prepare the PDF page.");
    }

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
    context.drawImage(
      canvas,
      0,
      start,
      canvas.width,
      sliceCanvas.height,
      0,
      0,
      canvas.width,
      sliceCanvas.height
    );

    const imageHeight = sliceCanvas.height * imageWidth / sliceCanvas.width;
    pdf.addImage(
      sliceCanvas.toDataURL("image/jpeg", 0.84),
      "JPEG",
      margin,
      margin,
      imageWidth,
      imageHeight,
      undefined,
      "FAST"
    );

    pdf.setFontSize(8);
    pdf.setTextColor(98, 116, 110);
    pdf.text(
      `FinIntel AI  |  ${index + 1} / ${slices.length}`,
      pageWidth - margin,
      pageHeight - 6,
      { align: "right" }
    );
  });

  pdf.save(
    `${safeFileName(title)}.pdf`
  );
}

function ReportCompanyCard({ company }: { company: Record<string, unknown> }) {
  const metrics = asRecord(company.key_metrics);

  return (
    <article className="report-company-card">
      <div className="section-heading-row">
        <div>
          <h3>{asString(company.company_name, "Company")}</h3>
          <span>{asString(company.ticker)}</span>
        </div>
      </div>

      <Panel title="Business Snapshot">{company.business_snapshot}</Panel>
      <div className="metric-grid">
        <Metric label="Current Price" value={metrics.current_price} />
        <Metric label="Market Cap" value={metrics.market_cap} />
        <Metric label="P/E" value={metrics.pe_ratio} />
        <Metric label="P/B" value={metrics.pb_ratio} />
        <Metric label="ROE" value={metrics.roe} />
        <Metric label="Profit Margin" value={metrics.profit_margin} />
        <Metric label="Revenue Growth" value={metrics.revenue_growth} />
        <Metric label="Debt/Equity" value={metrics.debt_to_equity} />
      </div>
      <Panel title="Financial Quality" tone="green">
        {company.financial_quality}
      </Panel>
      <Panel title="Valuation View" tone="blue">
        {company.valuation_view}
      </Panel>
      <ListPanel title="Growth Drivers" items={company.growth_drivers} tone="green" />
      <ListPanel title="Risks" items={company.risks} tone="red" />
      <Panel title="Analyst Takeaway">{company.analyst_takeaway}</Panel>
      <Sources sources={company.sources} compact />
    </article>
  );
}

function ReportMetricStrip({ companies }: { companies: Record<string, unknown>[] }) {
  const firstCompany = companies[0] || {};
  const metrics = asRecord(firstCompany.key_metrics);

  return (
    <div className="report-metric-strip">
      <Metric label="Company" value={firstCompany.company_name} />
      <Metric label="Ticker" value={firstCompany.ticker} />
      <Metric label="Market Cap" value={metrics.market_cap} />
      <Metric label="P/E Ratio" value={metrics.pe_ratio} />
    </div>
  );
}

function uniqueItems(items: string[]) {
  return Array.from(
    new Set(
      items
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
}

function reportInsights(
  payload: Record<string, unknown>,
  companies: Record<string, unknown>[]
) {
  const directInsights = flattenedList(payload.key_insights);

  if (directInsights.length) {
    return uniqueItems(directInsights).slice(0, 7);
  }

  const companyInsights = companies.flatMap((company) => [
    ...flattenedList(company.growth_drivers),
    asString(company.analyst_takeaway),
    asString(company.valuation_view),
  ]);

  return uniqueItems([
    ...companyInsights,
    ...flattenedList(payload.watchlist_triggers),
    ...flattenedList(payload.next_checks),
  ]).slice(0, 7);
}

function ReportDisclosure({
  number,
  title,
  description,
  defaultOpen = false,
  children,
  className = "",
}: {
  number: string;
  title: string;
  description?: string;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <details
      className={`report-disclosure ${className}`}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span className="report-disclosure-number">{number}</span>
        <span className="report-disclosure-heading">
          <strong>{title}</strong>
          {description && <small>{description}</small>}
        </span>
        <span className="report-disclosure-state" aria-hidden="true">
          {open ? "Hide" : "Show"}
        </span>
        <span className="report-disclosure-chevron" aria-hidden="true" />
      </summary>
      <div className="report-disclosure-content">{children}</div>
    </details>
  );
}

const COMPANY_METRICS = [
  ["current_price", "Current Price", "neutral"],
  ["market_cap", "Market Cap", "neutral"],
  ["pe_ratio", "P/E Ratio", "lower"],
  ["pb_ratio", "P/B Ratio", "lower"],
  ["roe", "ROE", "higher"],
  ["profit_margin", "Profit Margin", "higher"],
  ["revenue_growth", "Revenue Growth", "higher"],
  ["debt_to_equity", "Debt/Equity", "lower"],
] as const;

function comparableNumber(value: unknown) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const text = asString(value).toLowerCase();
  if (!text || text.includes("not ") || text.includes("n/a")) return null;

  const match = text.replaceAll(",", "").match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;

  const numeric = Number(match[0]);
  return Number.isFinite(numeric) ? numeric : null;
}

function metricLeaders(
  companies: Record<string, unknown>[],
  key: string,
  direction: "higher" | "lower" | "neutral"
) {
  if (direction === "neutral") return new Set<number>();

  const values = companies.map((company, index) => ({
    index,
    value: comparableNumber(asRecord(company.key_metrics)[key]),
  })).filter((item): item is { index: number; value: number } => item.value !== null);

  if (values.length < 2) return new Set<number>();

  const target = direction === "higher"
    ? Math.max(...values.map((item) => item.value))
    : Math.min(...values.map((item) => item.value));
  const tolerance = Math.max(Math.abs(target) * 0.0001, 0.0001);
  const leaders = values.filter((item) => Math.abs(item.value - target) <= tolerance);

  return leaders.length === values.length
    ? new Set<number>()
    : new Set(leaders.map((item) => item.index));
}

function ComparisonEdgeMap({
  companies,
  metrics,
}: {
  companies: Record<string, unknown>[];
  metrics: typeof COMPANY_METRICS[number][];
}) {
  const scores = companies.map(() => 0);
  let scoredMetrics = 0;

  metrics.forEach(([key, , direction]) => {
    const leaders = metricLeaders(companies, key, direction);
    if (!leaders.size) return;

    scoredMetrics += 1;
    leaders.forEach((index) => {
      scores[index] += 1;
    });
  });

  if (!scoredMetrics) return null;

  return (
    <div className="comparison-edge-map" aria-label="Metric leadership summary">
      <div className="comparison-edge-heading">
        <div>
          <span>FinIntel edge map</span>
          <strong>Metric leadership</strong>
        </div>
        <small>{scoredMetrics} comparable metric{scoredMetrics === 1 ? "" : "s"}</small>
      </div>
      <div className="comparison-edge-rows">
        {companies.map((company, index) => {
          const companyName = asString(company.company_name, `Company ${index + 1}`);
          const score = scores[index];
          const width = score > 0
            ? Math.max(4, (score / scoredMetrics) * 100)
            : 0;

          return (
            <div className="comparison-edge-row" key={`${companyName}-${index}`}>
              <span>{companyName}</span>
              <div aria-hidden="true">
                <i style={{ width: `${width}%` }} />
              </div>
              <strong>{score} lead{score === 1 ? "" : "s"}</strong>
            </div>
          );
        })}
      </div>
      <p>Directional metric count only. It does not represent an overall recommendation.</p>
    </div>
  );
}

function CompanyMetricComparison({
  companies,
}: {
  companies: Record<string, unknown>[];
}) {
  if (companies.length < 2) return null;

  const metrics = COMPANY_METRICS.filter(([key]) =>
    companies.some((company) => {
      const value = asRecord(company.key_metrics)[key];
      return value !== null && value !== undefined && value !== "";
    })
  );

  if (!metrics.length) return null;

  return (
    <section className="comparison-workspace" aria-labelledby="metric-comparison-title">
      <div className="comparison-workspace-heading">
        <div>
          <span>Side-by-side evidence</span>
          <h3 id="metric-comparison-title">Financial comparison</h3>
        </div>
        <small>{companies.length} companies</small>
      </div>
      <div className="comparison-legend">
        <span>Metric leader</span>
        <p>Metric-level comparison only; it is not an overall investment recommendation.</p>
      </div>
      <ComparisonEdgeMap companies={companies} metrics={metrics} />
      <div
        className="comparison-table-scroll"
        role="region"
        aria-label="Scrollable financial comparison table"
        tabIndex={0}
      >
        <table className="comparison-table comparison-table-metrics">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {companies.map((company, index) => (
                <th scope="col" key={`${asString(company.ticker, "company")}-${index}`}>
                  <strong>{asString(company.company_name, `Company ${index + 1}`)}</strong>
                  <small>{asString(company.ticker)}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map(([key, label, direction]) => {
              const leaders = metricLeaders(companies, key, direction);

              return (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  {companies.map((company, index) => {
                    const value = asRecord(company.key_metrics)[key];
                    const leads = leaders.has(index);
                    return (
                      <td
                        className={leads ? "comparison-leading-cell" : ""}
                        key={`${key}-${asString(company.ticker, String(index))}`}
                      >
                        {value === null || value === undefined || value === ""
                          ? <span className="data-status-missing">Not available</span>
                          : asString(value)}
                        {leads && <span className="comparison-lead-label">Metric leader</span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function companyRecordItems(
  record: Record<string, unknown>,
  company: string
) {
  const match = Object.entries(record).find(
    ([key]) => key.toLowerCase() === company.toLowerCase()
  );

  return match ? flattenedList(match[1]) : [];
}

function PeerDecisionTable({ payload }: { payload: Record<string, unknown> }) {
  const companies = asList(payload.companies_compared);
  const analyses = asList(payload.comparative_analysis);
  const strengths = asRecord(payload.strengths);
  const risks = asRecord(payload.risks);
  const winnerSummary = asString(payload.winner_summary);
  const summaryLower = winnerSummary.toLowerCase();
  const avoidsWinner = [
    "no winner",
    "no definitive",
    "no universal",
    "cannot be identified",
  ].some((phrase) => summaryLower.includes(phrase));
  const namedLeaders = avoidsWinner
    ? []
    : companies.filter((company) => summaryLower.includes(company.toLowerCase()));
  const indicatedLeader = namedLeaders.length === 1 ? namedLeaders[0] : "";

  if (companies.length < 2) return null;

  return (
    <section className="comparison-workspace" aria-labelledby="peer-comparison-title">
      <div className="comparison-workspace-heading">
        <div>
          <span>Decision matrix</span>
          <h3 id="peer-comparison-title">Peer comparison</h3>
        </div>
        <small>{companies.length} companies</small>
      </div>
      <div className="comparison-legend">
        <span>Model-indicated edge</span>
        <p>Shown only when the response identifies one company; review the balanced view and risks.</p>
      </div>
      <div
        className="comparison-table-scroll"
        role="region"
        aria-label="Scrollable peer comparison table"
        tabIndex={0}
      >
        <table className="comparison-table comparison-table-qualitative">
          <thead>
            <tr>
              <th scope="col">Company</th>
              <th scope="col">Key strength</th>
              <th scope="col">Main risk</th>
              <th scope="col">Analyst view</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((company, index) => {
              const companyStrengths = companyRecordItems(strengths, company);
              const companyRisks = companyRecordItems(risks, company);

              return (
                <tr
                  className={company === indicatedLeader ? "comparison-leading-row" : ""}
                  key={company}
                >
                  <th scope="row">
                    {company}
                    {company === indicatedLeader && (
                      <span className="comparison-lead-label">Model-indicated edge</span>
                    )}
                  </th>
                  <td>{companyStrengths.slice(0, 2).join("; ") || "Not highlighted"}</td>
                  <td>{companyRisks.slice(0, 2).join("; ") || "Not highlighted"}</td>
                  <td>{analyses[index] || "No company-specific assessment provided."}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReportInsightList({ insights }: { insights: string[] }) {
  if (!insights.length) return null;

  return (
    <ReportDisclosure
      number="01"
      title="Key Insights"
      description={`${insights.length} decision-relevant observations`}
      defaultOpen
      className="report-insights-card"
    >
      <div className="report-insight-list">
        {insights.map((insight) => (
          <div className="report-insight-row" key={insight}>
            <span />
            <p>{insight}</p>
          </div>
        ))}
      </div>
    </ReportDisclosure>
  );
}

function ReportTextCard({
  title,
  copy,
  tone = "neutral",
}: {
  title: string;
  copy: unknown;
  tone?: "neutral" | "green" | "amber" | "red";
}) {
  if (!copy) return null;

  return (
    <article className={`report-text-card report-text-card-${tone}`}>
      <h3>{title}</h3>
      <p>{asString(copy)}</p>
    </article>
  );
}

function PriceQuoteCard({
  payload,
  score,
  sourceCount,
}: {
  payload: Record<string, unknown>;
  score: number;
  sourceCount: number;
}) {
  const currency = asString(payload.currency, "INR");
  const numericPrice = asFiniteNumber(payload.current_price);
  const hasPrice = numericPrice !== null && numericPrice > 0;
  const change = asFiniteNumber(payload.change);
  const percentChange = asFiniteNumber(payload.percent_change);
  const changeTone = (percentChange ?? change ?? 0) > 0
    ? "positive"
    : (percentChange ?? change ?? 0) < 0
      ? "negative"
      : "neutral";
  const sourceUrl = (() => {
    try {
      const url = new URL(asString(payload.source_url));
      return ["http:", "https:"].includes(url.protocol) ? url.toString() : "";
    } catch {
      return "";
    }
  })();
  const asOf = payload.price_date
    ? asString(payload.price_date)
    : formatQuoteTime(payload.retrieved_at);
  const marketStatus = !hasPrice
    ? "Quote unavailable"
    : payload.is_market_open === true
      ? "Market open"
      : payload.is_market_open === false
        ? "Latest available"
        : freshnessLabel(payload);

  return (
    <section
      className={`price-quote-card ${hasPrice ? "" : "price-quote-card-unavailable"}`}
      aria-label="Price quote"
    >
      <header className="price-quote-header">
        <div>
          <span>Market quote</span>
          <h3>{getPayloadTitle("PRICE_QUERY", payload)}</h3>
          <p>
            {[asString(payload.ticker), asString(payload.exchange)]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <strong className="price-market-status">{marketStatus}</strong>
      </header>

      <div className="price-quote-value-row">
        <strong className="price-quote-value">
          {formatPrice(payload.current_price, currency)}
        </strong>
        {hasPrice && (change !== null || percentChange !== null) && (
          <span className={`price-change price-change-${changeTone}`}>
            {[formatSignedPrice(change, currency), formatSignedPercent(percentChange)]
              .filter(Boolean)
              .join(" · ")}
          </span>
        )}
      </div>

      <dl className="price-quote-meta">
        <div>
          <dt>Data provider</dt>
          <dd>{providerLabel(payload.provider)}</dd>
        </div>
        <div>
          <dt>Price as of</dt>
          <dd>{asOf}</dd>
        </div>
        <div>
          <dt>Data confidence</dt>
          <dd>{hasPrice && score > 0 ? `${formatPercent(score)} · ${confidenceLabel(score)}` : "Unavailable"}</dd>
        </div>
        <div>
          <dt>Evidence</dt>
          <dd>{sourceCount ? `${sourceCount} linked source${sourceCount === 1 ? "" : "s"}` : "Provider metadata only"}</dd>
        </div>
      </dl>

      <footer className="price-quote-footer">
        <span>{freshnessLabel(payload)}</span>
        {sourceUrl && (
          <a href={sourceUrl} target="_blank" rel="noreferrer">
            View quote source <span aria-hidden="true">↗</span>
          </a>
        )}
      </footer>
    </section>
  );
}

function ResultBody({
  route,
  payload,
  answerDetail,
}: {
  route: Route;
  payload: Record<string, unknown>;
  answerDetail: AnswerDetail;
}) {
  const detailed = answerDetail === "detailed";

  if (route === "REPORT") {
    const companies = asRecordList(payload.companies);
    const firstCompany = companies[0] || {};
    const insights = reportInsights(
      payload,
      companies
    );
    const watchlistTriggers = asList(payload.watchlist_triggers);
    const nextChecks = asList(payload.next_checks);
    const hasEvidence =
      asList(payload.sources_used).length > 0
      || Object.keys(asRecord(payload.confidence_breakdown)).length > 0;

    return (
      <div className="report-page">
        <ReportMetricStrip companies={companies} />

        <ReportDisclosure
          number="00"
          title="Stock Overview"
          description="Scope, thesis, and current context"
          defaultOpen
          className="report-overview"
        >
          <p>{asString(payload.stock_overview, asString(payload.executive_summary))}</p>
        </ReportDisclosure>

        <ReportInsightList insights={insights} />

        <CompanyMetricComparison companies={companies} />

        <ReportDisclosure
          number="02"
          title="Performance, Risk & Valuation"
          description="Core factors that shape the investment view"
          defaultOpen
        >
          <div className="report-three-grid">
            <ReportTextCard
              title="Current Performance"
              copy={
                asString(payload.current_performance)
                || asString(firstCompany.business_snapshot)
                || asString(firstCompany.financial_quality)
                || payload.sector_context
              }
              tone="green"
            />
            <ReportTextCard
              title="Risk Assessment"
              copy={
                asString(payload.risk_assessment)
                || flattenedList(payload.key_risks || firstCompany.risks).join(" ")
              }
              tone="red"
            />
            <ReportTextCard
              title="Valuation & Outlook"
              copy={
                asString(payload.valuation_outlook)
                || asString(firstCompany.valuation_view)
                || asString(payload.comparative_view)
                || asString(payload.investment_view)
              }
              tone="amber"
            />
          </div>
        </ReportDisclosure>

        <ReportDisclosure
          number="03"
          title="Research Context"
          description="Sector backdrop and source-quality assessment"
        >
          <div className="report-two-grid">
            <Panel title="Research View" tone="green">
              {payload.research_view || payload.investment_view}
            </Panel>
            <Panel title="Sector Context" tone="blue">
              {payload.sector_context}
            </Panel>
          </div>

          <Panel title="Source Quality" tone="blue">
            {asString(
              asRecord(payload.source_quality).quality_view,
              sourceCountText(payload.sources_used)
            )}
          </Panel>
        </ReportDisclosure>

        {companies.length > 1 && (
          <ReportDisclosure
            number="04"
            title="Company Details"
            description={`Deep dive across ${companies.length} companies`}
          >
            {companies.map((company, index) => (
              <ReportCompanyCard
                company={company}
                key={`${asString(company.ticker, "company")}-${index}`}
              />
            ))}
          </ReportDisclosure>
        )}

        {(watchlistTriggers.length > 0 || nextChecks.length > 0) && (
          <ReportDisclosure
            number="05"
            title="Monitoring Plan"
            description="Triggers and diligence steps to track next"
          >
            <div className="report-two-grid">
              <ListPanel title="Watchlist Triggers" items={payload.watchlist_triggers} tone="green" />
              <ListPanel title="Next Checks" items={payload.next_checks} />
            </div>
          </ReportDisclosure>
        )}

        {hasEvidence && (
          <ReportDisclosure
            number="06"
            title="Evidence & Confidence"
            description="Source links and confidence methodology"
          >
            <Sources sources={payload.sources_used} />
            <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
          </ReportDisclosure>
        )}
      </div>
    );
  }

  if (route === "PRICE_QUERY") {
    return (
      <>
        <Panel title="Quote context" tone="blue">
          {payload.message}
        </Panel>
        <div className="metric-grid price-detail-grid">
          <Metric label="Previous Close" value={formatPrice(payload.previous_close, asString(payload.currency, "INR"))} />
          <Metric label="Day Open" value={formatPrice(payload.day_open, asString(payload.currency, "INR"))} />
          <Metric
            label="Day Range"
            value={
              payload.day_low !== null && payload.day_low !== undefined
              && payload.day_high !== null && payload.day_high !== undefined
                ? `${formatPrice(payload.day_low, asString(payload.currency, "INR"))} – ${formatPrice(payload.day_high, asString(payload.currency, "INR"))}`
                : "Unavailable"
            }
          />
          <Metric label="Volume" value={formatCompactNumber(payload.volume)} />
          <Metric label="P/E Ratio" value={payload.pe_ratio} />
          <Metric label="Market Cap" value={payload.market_cap} />
          <Metric label="Sector" value={payload.sector} />
        </div>
        {detailed && <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />}
      </>
    );
  }

  if (route === "EDUCATIONAL") {
    return (
      <>
        <Panel title="Simple Definition">{payload.simple_definition}</Panel>
        {detailed && (
          <Panel title="Detailed Explanation">{payload.detailed_explanation}</Panel>
        )}
        <Panel title="Why It Matters" tone="green">
          {payload.why_it_matters}
        </Panel>
        {detailed && (
          <>
            <Panel title="Practical Interpretation" tone="blue">
              {payload.practical_interpretation}
            </Panel>
            <Panel title="Limitations" tone="red">
              {payload.limitations}
            </Panel>
          </>
        )}
        <Panel title="Example" tone="blue">
          {payload.example}
        </Panel>
        {detailed && (
          <>
            <Sources sources={payload.sources_used} />
            <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
          </>
        )}
      </>
    );
  }

  if (route === "DISCOVERY") {
    return (
      <>
        <Panel title="Market Overview">{payload.summary}</Panel>
        <ListPanel title="Key Points" items={payload.key_points} />
        {detailed && (
          <>
            <ListPanel title="Companies To Explore" items={payload.mentioned_companies} />
            <Sources sources={payload.sources_used} />
            <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
          </>
        )}
      </>
    );
  }

  if (route === "NEWS") {
    return (
      <>
        <Panel title="Headline Summary">{payload.headline_summary}</Panel>
        <Panel title="Market Impact" tone="blue">
          {payload.market_impact}
        </Panel>
        <StatPill label="Sentiment" value={payload.sentiment} />
        {detailed && (
          <>
            <ListPanel title="Key Events" items={payload.key_events} />
            <ListPanel title="Risk Factors" items={payload.risk_factors} tone="red" />
            <Sources sources={payload.sources} />
            <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
          </>
        )}
      </>
    );
  }

  if (route === "COMPARISON") {
    return (
      <>
        <Panel title="Summary">{payload.summary}</Panel>
        <Panel title="Winner Summary" tone="green">
          {payload.winner_summary}
        </Panel>
        <PeerDecisionTable payload={payload} />
        {detailed && (
          <>
            <ReportDisclosure
              number="01"
              title="Detailed Comparison"
              description="Company-level analysis, strengths, and risks"
              defaultOpen
            >
              <ListPanel title="Comparative Analysis" items={payload.comparative_analysis} />
              <div className="report-two-grid">
                <ListPanel title="Strengths" items={Object.values(asRecord(payload.strengths)).flat()} tone="green" />
                <ListPanel title="Risks" items={Object.values(asRecord(payload.risks)).flat()} tone="red" />
              </div>
              <Panel title="Balanced View">{payload.balanced_view}</Panel>
            </ReportDisclosure>
            <ReportDisclosure
              number="02"
              title="Evidence & Confidence"
              description="Source links and confidence methodology"
            >
              <Sources sources={payload.sources_used} />
              <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
            </ReportDisclosure>
          </>
        )}
      </>
    );
  }

  return (
    <>
      <Panel title="Business Overview">{payload.business_overview}</Panel>
      <Panel title="Overall View">{payload.overall_view}</Panel>
      {detailed && (
        <>
          <ListPanel title="Strengths" items={payload.financial_strengths} tone="green" />
          <ListPanel title="Risks" items={payload.financial_risks} tone="red" />
          <Panel title="Valuation Commentary" tone="blue">
            {payload.valuation_commentary}
          </Panel>
          <Sources sources={payload.sources_used} />
          <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
        </>
      )}
    </>
  );
}

function InvestmentSnapshot({
  route,
  payload,
  score,
  sourceCount,
  canExport,
  exporting,
  onExportPdf,
}: {
  route: Route;
  payload: Record<string, unknown>;
  score: number;
  sourceCount: number;
  canExport: boolean;
  exporting: boolean;
  onExportPdf: () => void;
}) {
  const confidencePercent = Math.round(score * 100);
  const hasConfidence = score > 0;
  const signal = getResearchSignal(route, payload, score, sourceCount);
  const guardrails = asRecord(payload.guardrails);
  const sourceQuality = asRecord(guardrails.source_quality);
  const dataQuality = asRecord(guardrails.data_quality);
  const declaredSourceQuality = asString(sourceQuality.label).toLowerCase();
  const evidenceIsSupported = ["strong", "high", "good", "verified"].some(
    (label) => declaredSourceQuality.includes(label)
  ) || (sourceCount >= 2 && score >= 0.7);
  const evidenceLabel = sourceCount > 0 && evidenceIsSupported
    ? "Supported evidence"
    : sourceCount > 0
      ? "Partial coverage"
      : "Evidence unavailable";
  const snapshotItems = [
    {
      key: "view",
      label: "View",
      value: getSnapshotView(route, payload),
    },
    {
      key: "reason",
      label: "Key reason",
      value: getSnapshotReason(route, payload),
      wide: true,
    },
    {
      key: "confidence",
      label: "Analysis confidence",
      value: hasConfidence
        ? `${confidencePercent}% (${confidenceLabel(score)})`
        : "Not provided",
    },
    {
      key: "risk",
      label: "Main risk",
      value: getSnapshotRisk(payload),
      wide: true,
    },
    {
      key: "sources",
      label: "Source count",
      value: sourceCount
        ? `${sourceCount} source link${sourceCount === 1 ? "" : "s"}`
        : "Not provided",
    },
  ];

  return (
    <section className="investment-snapshot" aria-label="Investment snapshot">
      <div className="investment-snapshot-header">
        <div>
          <span>FinIntel / Investment Snapshot</span>
          <h3>{getPayloadTitle(route, payload)}</h3>
        </div>
        <div className="investment-snapshot-actions">
          <div className={`research-signal research-signal-${signal.tone}`}>
            <span>Research signal</span>
            <strong>{signal.label}</strong>
            <small>{signal.detail}</small>
          </div>
          {canExport && (
            <button
              type="button"
              onClick={onExportPdf}
              disabled={exporting}
            >
              <span aria-hidden="true">↓</span>
              {exporting ? "Preparing PDF..." : "Export PDF"}
            </button>
          )}
        </div>
      </div>
      <div className="investment-snapshot-grid">
        {snapshotItems.map((item) => (
          <article
            className={`investment-snapshot-item investment-snapshot-item-${item.key} ${item.wide ? "investment-snapshot-item-wide" : ""}`}
            key={item.key}
          >
            <span>{item.label}</span>
            <strong>{conciseSnapshotText(item.value)}</strong>
          </article>
        ))}
      </div>
      <div className={`evidence-stamp evidence-stamp-${sourceCount ? "linked" : "limited"}`}>
        <div className="evidence-stamp-mark" aria-hidden="true">FI</div>
        <div>
          <span>Evidence quality</span>
          <strong>{evidenceLabel}</strong>
          <small>
            {sourceCount ? `${sourceCount} linked source${sourceCount === 1 ? "" : "s"}` : "No linked sources"}
            {hasConfidence ? ` · ${confidencePercent}% analysis confidence` : " · Analysis confidence unavailable"}
            {dataQuality.label ? ` · ${asString(dataQuality.label)} data` : ""}
          </small>
        </div>
        <em>{asString(sourceQuality.label, sourceCount ? "Linked" : "Limited")}</em>
      </div>
    </section>
  );
}

function AssistantResultMessage({
  result,
  fallbackDetail,
  mode = "chat",
}: {
  result: ApiResult;
  fallbackDetail: AnswerDetail;
  mode?: WorkMode;
}) {
  const exportRef = useRef<HTMLElement | null>(null);
  const snapshotRef = useRef<HTMLDivElement | null>(null);
  const analysisRef = useRef<HTMLElement | null>(null);
  const sourcesRef = useRef<HTMLDivElement | null>(null);
  const [exporting, setExporting] = useState(false);
  const payload = result.response?.data || {};
  const score = getConfidenceScore(payload);
  const sources = Array.from(new Set([
    ...asList(payload.sources_used),
    ...asList(payload.sources),
    ...asList(payload.source_url),
  ]));
  const sourceCount = sources.length;
  const isPriceQuery = result.route === "PRICE_QUERY";
  const isReport = mode === "report";
  const canExport =
    isReport
    || (result.answer_detail || fallbackDetail) === "detailed";
  const reportTitle = `${getPayloadTitle(result.route, payload)} ${routeLabel(result.route)}`;

  async function handleExportPdf() {
    if (!exportRef.current) return;

    setExporting(true);

    try {
      await exportElementToPdf(
        exportRef.current,
        reportTitle,
        isReport
      );
    } finally {
      setExporting(false);
    }
  }

  function scrollToSection(ref: { current: HTMLElement | null }) {
    ref.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  }

  return (
    <section
      className={`result-shell assistant-message ${isReport ? "report-result" : ""}`}
      ref={exportRef}
    >
      <div className="result-section-anchor" ref={snapshotRef}>
        {isPriceQuery ? (
          <PriceQuoteCard
            payload={payload}
            score={score}
            sourceCount={sourceCount}
          />
        ) : (
          <InvestmentSnapshot
            route={result.route}
            payload={payload}
            score={score}
            sourceCount={sourceCount}
            canExport={canExport}
            exporting={exporting}
            onExportPdf={handleExportPdf}
          />
        )}
      </div>
      <div className="result-section-nav" role="navigation" aria-label="Result sections">
        <button type="button" onClick={() => scrollToSection(snapshotRef)}>
          {isPriceQuery ? "Quote" : "Snapshot"}
        </button>
        <button type="button" onClick={() => scrollToSection(analysisRef)}>
          Analysis
        </button>
        {sourceCount > 0 && (
          <button type="button" onClick={() => scrollToSection(sourcesRef)}>
            Sources <span>{sourceCount}</span>
          </button>
        )}
      </div>
      {isReport && (
        <div className="report-cover">
          <span>FinIntel analyst report</span>
          <h2>{getPayloadTitle(result.route, payload)}</h2>
          <p>{result.query}</p>
        </div>
      )}
      <section className="answer-overview" ref={analysisRef}>
        <div className="summary-topline">
          <span className={`badge ${isReport ? "badge-report" : ""}`}>
            {modeLabel(mode)}
          </span>
          <span className="badge">{routeLabel(result.route)}</span>
          <span className="badge badge-muted">
            {(result.answer_detail || fallbackDetail) === "detailed" ? "Detailed" : "Brief"}
          </span>
          {Boolean(payload.ticker) && (
            <span className="ticker">{asString(payload.ticker)}</span>
          )}
        </div>
        <p className="answer-query">{result.query}</p>
        <p className="answer-lede">
          {asString(
            getRouteSummary(result.route, payload),
            result.routing?.reasoning || "Route selected by query analysis."
          )}
        </p>
        <div className="result-meta">
          <StatPill label="Route" value={routeLabel(result.route)} />
          <StatPill
            label="Linked evidence"
            value={sourceCount ? sourceCount : payload.provider ? "Provider identified" : "Evidence unavailable"}
          />
          <StatPill
            label={isPriceQuery ? "Data confidence" : "Analysis confidence"}
            value={score > 0 ? formatPercent(score) : "Not provided"}
          />
          <StatPill label="Routing confidence" value={formatPercent(result.routing?.confidence)} />
        </div>
      </section>

      {sourceCount > 0 && (
        <div className="result-section-anchor" ref={sourcesRef}>
          <Sources
            sources={sources}
            compact
          />
        </div>
      )}

      <GuardrailNotice guardrails={payload.guardrails} />

      {canExport && result.route !== "REPORT" && (
        <AnalystReportTemplate
          route={result.route}
          payload={payload}
        />
      )}

      <ResultBody
        route={result.route}
        payload={payload}
        answerDetail={result.answer_detail || fallbackDetail}
      />

      {Boolean(payload.disclaimer) && (
        <footer className="disclaimer">
          <strong>Disclaimer:</strong> {asString(payload.disclaimer)}
        </footer>
      )}
    </section>
  );
}

export { AssistantResultMessage };
