import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";

const BACKEND_API_URL =
  import.meta.env.VITE_BACKEND_API_URL || "http://127.0.0.1:8000";
const APP_API_KEY = import.meta.env.VITE_APP_API_KEY || "";

const EXAMPLES = [
  "What is ROE?",
  "Current price of HDFC Bank",
  "Compare HDFC Bank vs ICICI Bank",
  "Top undervalued IT stocks in India",
  "Latest news about Infosys",
  "Fundamental analysis of TCS",
];

const REPORT_EXAMPLES = [
  "Generate a fundamental report on TCS",
  "Compare HDFC Bank and ICICI Bank as an investment report",
  "Create a report on undervalued IT stocks in India",
  "Prepare a news impact report for Infosys",
];

const ROUTE_LABELS: Record<string, string> = {
  PRICE_QUERY: "Price Check",
  EDUCATIONAL: "Learning",
  DISCOVERY: "Discovery",
  NEWS: "News",
  COMPARISON: "Comparison",
  FUNDAMENTAL: "Fundamentals",
  REPORT: "Analyst Report",
};

type Route =
  | "PRICE_QUERY"
  | "EDUCATIONAL"
  | "DISCOVERY"
  | "NEWS"
  | "COMPARISON"
  | "FUNDAMENTAL"
  | "REPORT"
  | string;

type ApiResult = {
  success: boolean;
  query: string;
  conversation_id?: string;
  answer_detail?: AnswerDetail;
  route: Route;
  routing?: {
    confidence?: number;
    reasoning?: string;
  };
  query_intelligence?: Record<string, unknown>;
  response?: {
    success: boolean;
    data?: Record<string, unknown>;
    error?: string | null;
  };
  error?: string;
  model?: string;
};

type AnswerDetail = "brief" | "detailed";

type WorkMode = "chat" | "report";

const MODE_COPY: Record<
  WorkMode,
  {
    eyebrow: string;
    title: string;
    welcome: string;
    placeholder: string;
    loading: string;
    submit: string;
  }
> = {
  chat: {
    eyebrow: "AI equity research, grounded with sources",
    title: "Research chat",
    welcome:
      "Ask about prices, ratios, company fundamentals, comparisons, discovery screens, or news context.",
    placeholder: "Ask about HDFC Bank, ROE, IT stocks, or latest market news",
    loading: "Routing, retrieving sources, and preparing a grounded answer.",
    submit: "Analyze",
  },
  report: {
    eyebrow: "Structured research briefs with export",
    title: "Report generator",
    welcome:
      "Enter a company, comparison, sector, or market theme to generate a structured analyst-style report.",
    placeholder:
      "Enter companies or a theme, e.g. HDFC Bank vs ICICI Bank or undervalued IT stocks",
    loading: "Routing, retrieving sources, and assembling a structured report.",
    submit: "Generate report",
  },
};

type AuthUser = {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
};

type AuthResult = {
  success: boolean;
  access_token?: string;
  token_type?: string;
  user?: AuthUser;
  error?: string;
};

type ChatHistoryItem = {
  id: number;
  query: string;
  route: string;
  routing?: ApiResult["routing"] | null;
  query_intelligence?: Record<string, unknown> | null;
  response?: ApiResult["response"] | null;
  answer_detail?: AnswerDetail | null;
  model?: string | null;
  response_success: boolean;
  response_error?: string | null;
  confidence_score?: number | null;
  created_at: number;
};

type ConversationSummary = {
  conversation_id: string;
  title: string;
  created_at: number;
  updated_at: number;
};

type StoredConversationMessage = {
  id: number;
  conversation_id: string;
  role: "user" | "assistant" | "error";
  content: string;
  payload?: ApiResult | null;
  created_at: number;
};

type ProgressEvent = {
  step: string;
  index: number;
  total: number;
};

type ChatMessage =
  | {
      id: string;
      role: "user";
      content: string;
      mode?: WorkMode;
    }
  | {
      id: string;
      role: "assistant";
      result: ApiResult;
      mode?: WorkMode;
    }
  | {
      id: string;
      role: "error";
      content: string;
    };

type ExternalAuth = {
  enabled: boolean;
  isLoaded: boolean;
  isSignedIn: boolean;
  email: string;
  fullName: string;
  getToken: () => Promise<string | null>;
  signOut: () => Promise<void>;
  controls: ReactNode;
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
  if (!Number.isFinite(numeric)) return value || "Unavailable";

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numeric);
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

function newMessageId(role: ChatMessage["role"]) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${role}-${crypto.randomUUID()}`;
  }

  return `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function messagesFromHistoryItem(
  item: ChatHistoryItem
): ChatMessage[] {
  const userMessage: ChatMessage = {
    id: newMessageId("user"),
    role: "user",
    content: item.query,
  };

  if (!item.response) {
    return [
      userMessage,
    ];
  }

  const assistantResult: ApiResult = {
    success: true,
    query: item.query,
    answer_detail: item.answer_detail || "brief",
    route: item.route,
    routing: item.routing || undefined,
    query_intelligence: item.query_intelligence || undefined,
    response: item.response,
  };

  if (!item.response_success) {
    return [
      userMessage,
      {
        id: newMessageId("error"),
        role: "error",
        content: item.response_error || item.response.error || "Analysis failed.",
      },
    ];
  }

  return [
    userMessage,
    {
      id: newMessageId("assistant"),
      role: "assistant",
      result: assistantResult,
    },
  ];
}

function messagesFromStoredConversation(
  storedMessages: StoredConversationMessage[]
): ChatMessage[] {
  return storedMessages.reduce<ChatMessage[]>((items, message) => {
    if (message.role === "user") {
      items.push(
        {
          id: `stored-user-${message.id}`,
          role: "user",
          content: message.content,
        }
      );
      return items;
    }

    if (message.payload?.response?.success) {
      items.push(
        {
          id: `stored-assistant-${message.id}`,
          role: "assistant",
          result: message.payload,
        }
      );
      return items;
    }

    items.push(
      {
        id: `stored-error-${message.id}`,
        role: "error",
        content:
          message.payload?.response?.error
          || message.content
          || "Analysis failed.",
      }
    );

    return items;
  }, []);
}

function getConfidenceScore(
  payload: Record<string, unknown>,
  result: ApiResult | null
) {
  const payloadScore = Number(payload.confidence_score);
  if (Number.isFinite(payloadScore) && payloadScore > 0) return payloadScore;

  const routingScore = Number(result?.routing?.confidence);
  if (Number.isFinite(routingScore) && routingScore > 0) return routingScore;

  return 0;
}

function confidenceLabel(score: number) {
  if (score >= 0.85) return "Very high";
  if (score >= 0.7) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
}

function progressPercent(events: ProgressEvent[]) {
  const latest = events[events.length - 1];

  if (latest?.total && latest.total > 0) {
    return Math.min(
      96,
      Math.max(
        16,
        Math.round((latest.index / latest.total) * 100)
      )
    );
  }

  return events.length ? 52 : 16;
}

function formatHistoryDate(value: number) {
  const timestamp = value > 10_000_000_000 ? value : value * 1000;
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
  }).format(date);
}

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

async function fetchAnalysis(
  query: string,
  token: string,
  answerDetail: AnswerDetail,
  conversationContext: ChatMessage[],
  conversationId: string,
  mode: WorkMode
): Promise<ApiResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    headers["X-API-Key"] = APP_API_KEY;
  }

  const endpoint = mode === "report" ? "report" : "chat";

  const response = await fetch(`${BACKEND_API_URL}/${endpoint}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      answer_detail: answerDetail,
      conversation_id: conversationId || null,
      conversation_context: conversationContext
        .slice(-8)
        .map((message) => ({
          role: message.role,
          content:
            message.role === "assistant"
              ? message.result.query
              : message.content,
        })),
    }),
  });

  const body = (await response.json().catch(() => null)) as ApiResult | null;

  if (!response.ok) {
    throw new Error(body?.error || `Backend returned ${response.status}`);
  }

  if (!body) {
    throw new Error("Backend returned an invalid JSON response.");
  }

  return body;
}

async function fetchAnalysisStream(
  query: string,
  token: string,
  answerDetail: AnswerDetail,
  conversationContext: ChatMessage[],
  conversationId: string,
  mode: WorkMode,
  onProgress: (progress: ProgressEvent) => void
): Promise<ApiResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    headers["X-API-Key"] = APP_API_KEY;
  }

  const endpoint = mode === "report" ? "report/stream" : "chat/stream";

  const response = await fetch(`${BACKEND_API_URL}/${endpoint}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      answer_detail: answerDetail,
      conversation_id: conversationId || null,
      conversation_context: conversationContext
        .slice(-8)
        .map((message) => ({
          role: message.role,
          content:
            message.role === "assistant"
              ? message.result.query
              : message.content,
        })),
    }),
  });

  if (!response.ok || !response.body) {
    return fetchAnalysis(
      query,
      token,
      answerDetail,
      conversationContext,
      conversationId,
      mode
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), {
      stream: !done,
    });

    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const lines = rawEvent.split("\n");
      const eventType = lines
        .find((line) => line.startsWith("event: "))
        ?.slice(7)
        .trim();
      const dataLine = lines
        .find((line) => line.startsWith("data: "))
        ?.slice(6);

      if (!eventType || !dataLine) continue;

      const payload = JSON.parse(dataLine);

      if (eventType === "progress") {
        onProgress(payload as ProgressEvent);
      }

      if (eventType === "final") {
        return payload as ApiResult;
      }

      if (eventType === "error") {
        throw new Error(payload.error || "Analysis failed.");
      }
    }

    if (done) break;
  }

  throw new Error("Streaming response ended before a final answer.");
}

async function fetchConversations(token: string): Promise<ConversationSummary[]> {
  if (!token) return [];

  const response = await fetch(`${BACKEND_API_URL}/chat/conversations?limit=20`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !body?.success) {
    return [];
  }

  return body.conversations || [];
}

async function fetchConversationMessages(
  token: string,
  conversationId: string
): Promise<StoredConversationMessage[]> {
  if (!token || !conversationId) return [];

  const response = await fetch(`${BACKEND_API_URL}/chat/conversations/${conversationId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !body?.success) {
    return [];
  }

  return body.messages || [];
}

async function submitAuth(
  mode: "login" | "register",
  email: string,
  password: string,
  fullName: string
): Promise<AuthResult> {
  const response = await fetch(`${BACKEND_API_URL}/auth/${mode}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
      full_name: fullName,
    }),
  });

  const body = (await response.json().catch(() => null)) as AuthResult | null;

  if (!response.ok) {
    throw new Error(body?.error || `Auth failed with ${response.status}`);
  }

  if (!body?.access_token || !body.user) {
    throw new Error("Authentication response was incomplete.");
  }

  return body;
}

async function fetchHistory(token: string): Promise<ChatHistoryItem[]> {
  if (!token) return [];

  const response = await fetch(`${BACKEND_API_URL}/chat/history?limit=8`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !body?.success) {
    return [];
  }

  return body.history || [];
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
        <h3>{compact ? "Verified sources" : "Sources"}</h3>
        <span>{list.length} link{list.length === 1 ? "" : "s"}</span>
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
        <strong>Financial safety checks</strong>
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
    <section className="analyst-template">
      <div className="section-heading-row">
        <h3>Analyst Report</h3>
        <span>Structured detailed view</span>
      </div>

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
    </section>
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

function TrustStrip() {
  return (
    <div className="trust-strip" aria-label="Supported workflows">
      <span>Grounded sources</span>
      <span>Live market data</span>
      <span>Comparison-ready</span>
      <span>Saved research</span>
    </div>
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
  title: string
) {
  const [
    { default: html2canvas },
    { default: jsPDF }
  ] = await Promise.all([
    import("html2canvas"),
    import("jspdf")
  ]);

  const canvas = await html2canvas(
    element,
    {
      backgroundColor: "#f6f8f7",
      scale: 2,
      useCORS: true
    }
  );
  const image = canvas.toDataURL(
    "image/png"
  );
  const pdf = new jsPDF(
    "p",
    "mm",
    "a4"
  );
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 10;
  const imageWidth = pageWidth - margin * 2;
  const imageHeight = (
    canvas.height
    * imageWidth
  ) / canvas.width;
  let remainingHeight = imageHeight;
  let position = margin;

  pdf.addImage(
    image,
    "PNG",
    margin,
    position,
    imageWidth,
    imageHeight
  );
  remainingHeight -= pageHeight - margin * 2;

  while (remainingHeight > 0) {
    position = remainingHeight - imageHeight + margin;
    pdf.addPage();
    pdf.addImage(
      image,
      "PNG",
      margin,
      position,
      imageWidth,
      imageHeight
    );
    remainingHeight -= pageHeight - margin * 2;
  }

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

function ReportInsightList({ insights }: { insights: string[] }) {
  if (!insights.length) return null;

  return (
    <section className="report-section report-insights-card">
      <div className="report-section-title">
        <span>01</span>
        <h3>Key Insights</h3>
      </div>
      <div className="report-insight-list">
        {insights.map((insight) => (
          <div className="report-insight-row" key={insight}>
            <span />
            <p>{insight}</p>
          </div>
        ))}
      </div>
    </section>
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
    const companies = asList(payload.companies)
      .map((company) => asRecord(company))
      .filter((company) => Object.keys(company).length > 0);
    const firstCompany = companies[0] || {};
    const insights = reportInsights(
      payload,
      companies
    );

    return (
      <div className="report-page">
        <ReportMetricStrip companies={companies} />

        <section className="report-section report-overview">
          <div className="report-section-title">
            <span>00</span>
            <h3>Stock Overview</h3>
          </div>
          <p>{asString(payload.stock_overview, asString(payload.executive_summary))}</p>
        </section>

        <ReportInsightList insights={insights} />

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

        {companies.length > 1 && (
          <section className="report-section">
            <div className="report-section-title">
              <span>02</span>
              <h3>Company Details</h3>
            </div>
            {companies.map((company, index) => (
              <ReportCompanyCard
                company={company}
                key={`${asString(company.ticker, "company")}-${index}`}
              />
            ))}
          </section>
        )}

        <div className="report-two-grid">
          <ListPanel title="Watchlist Triggers" items={payload.watchlist_triggers} tone="green" />
          <ListPanel title="Next Checks" items={payload.next_checks} />
        </div>

        <Sources sources={payload.sources_used} />
        <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
      </div>
    );
  }

  if (route === "PRICE_QUERY") {
    return (
      <>
        <Panel title="Current Trading Information" tone="blue">
          {payload.message}
        </Panel>
        <div className="metric-grid">
          <Metric
            label="Current Price"
            value={formatPrice(payload.current_price, asString(payload.currency, "INR"))}
          />
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
        {detailed && (
          <>
            <ListPanel title="Comparative Analysis" items={payload.comparative_analysis} />
            <ListPanel title="Strengths" items={Object.values(asRecord(payload.strengths)).flat()} tone="green" />
            <ListPanel title="Risks" items={Object.values(asRecord(payload.risks)).flat()} tone="red" />
            <Panel title="Balanced View">{payload.balanced_view}</Panel>
            <Sources sources={payload.sources_used} />
            <ConfidenceBreakdown breakdown={payload.confidence_breakdown} />
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
  const snapshotItems = [
    {
      label: "View",
      value: getSnapshotView(route, payload),
    },
    {
      label: "Key reason",
      value: getSnapshotReason(route, payload),
      wide: true,
    },
    {
      label: "Confidence",
      value: hasConfidence
        ? `${confidencePercent}% (${confidenceLabel(score)})`
        : "Not provided",
    },
    {
      label: "Main risk",
      value: getSnapshotRisk(payload),
      wide: true,
    },
    {
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
          <span>Investment Snapshot</span>
          <h3>{getPayloadTitle(route, payload)}</h3>
        </div>
        {canExport && (
          <button
            type="button"
            onClick={onExportPdf}
            disabled={exporting}
          >
            {exporting ? "Preparing PDF..." : "Export PDF"}
          </button>
        )}
      </div>
      <div className="investment-snapshot-grid">
        {snapshotItems.map((item) => (
          <article
            className={`investment-snapshot-item ${item.wide ? "investment-snapshot-item-wide" : ""}`}
            key={item.label}
          >
            <span>{item.label}</span>
            <strong>{conciseSnapshotText(item.value)}</strong>
          </article>
        ))}
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
  const [exporting, setExporting] = useState(false);
  const payload = result.response?.data || {};
  const score = getConfidenceScore(payload, result);
  const sourceCount = asList(payload.sources_used || payload.sources).length;
  const sources = payload.sources_used || payload.sources;
  const isReport = mode === "report";
  const confidencePercent = Math.round(score * 100);
  const hasConfidence = score > 0;
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
        reportTitle
      );
    } finally {
      setExporting(false);
    }
  }

  return (
    <section
      className={`result-shell assistant-message ${isReport ? "report-result" : ""}`}
      ref={exportRef}
    >
      <InvestmentSnapshot
        route={result.route}
        payload={payload}
        score={score}
        sourceCount={sourceCount}
        canExport={canExport}
        exporting={exporting}
        onExportPdf={handleExportPdf}
      />
      {isReport && (
        <div className="report-cover">
          <span>FinIntel analyst report</span>
          <h2>{getPayloadTitle(result.route, payload)}</h2>
          <p>{result.query}</p>
        </div>
      )}
      <div className="summary-grid">
        <section className="summary-card">
          <div className="summary-topline">
            <span className={`badge ${isReport ? "badge-report" : ""}`}>
              {modeLabel(mode)}
            </span>
            <span className="badge">{routeLabel(result.route)}</span>
            <span className="badge badge-muted">
              {(result.answer_detail || fallbackDetail) === "detailed" ? "Detailed" : "Brief"}
            </span>
            <span className="muted">{result.query}</span>
          </div>
          <h2>{getPayloadTitle(result.route, payload)}</h2>
          {Boolean(payload.ticker) && (
            <p className="ticker">{asString(payload.ticker)}</p>
          )}
          <p>
            {asString(
              getRouteSummary(result.route, payload),
              result.routing?.reasoning || "Route selected by query analysis."
            )}
          </p>
          <div className="result-meta">
            <StatPill label="Route" value={routeLabel(result.route)} />
            <StatPill label="Verified sources" value={sourceCount ? sourceCount : "Not provided"} />
            <StatPill label="Routing confidence" value={formatPercent(result.routing?.confidence)} />
          </div>
        </section>

        <section
          className="confidence-card"
          aria-label={
            hasConfidence
              ? `Confidence score ${confidencePercent} percent`
              : "Confidence score not provided"
          }
        >
          <span>Confidence</span>
          <strong>{hasConfidence ? `${confidencePercent}%` : "N/A"}</strong>
          <small>{hasConfidence ? confidenceLabel(score) : "Not provided"}</small>
          <div
            className="meter"
            role="meter"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={hasConfidence ? confidencePercent : undefined}
            aria-label="Confidence score"
          >
            <div style={{ width: `${hasConfidence ? confidencePercent : 0}%` }} />
          </div>
        </section>
      </div>

      {sourceCount > 0 && (
        <Sources
          sources={sources}
          compact
        />
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

export default function App({
  externalAuth,
}: {
  externalAuth?: ExternalAuth;
}) {
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authOpen, setAuthOpen] = useState(false);
  const [answerDetail, setAnswerDetail] = useState<AnswerDetail>("brief");
  const [workMode, setWorkMode] = useState<WorkMode>("chat");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [token, setToken] = useState(() => localStorage.getItem("finintel_token") || "");
  const [currentConversationId, setCurrentConversationId] = useState("");
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem("finintel_user");
    return stored ? (JSON.parse(stored) as AuthUser) : null;
  });
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const externalSignedIn = Boolean(
    externalAuth?.enabled && externalAuth.isSignedIn
  );
  const displayedUser = externalAuth?.enabled
    ? externalSignedIn
      ? {
          full_name: externalAuth.fullName,
          email: externalAuth.email,
        }
      : null
    : user;

  const modeCopy = MODE_COPY[workMode];
  const modeExamples = workMode === "report" ? REPORT_EXAMPLES : EXAMPLES;
  const activeConversation = conversations.find(
    (item) => item.conversation_id === currentConversationId
  );
  const progressValue = progressPercent(progressEvents);
  const authStatus = externalAuth?.enabled
    ? externalSignedIn
      ? "Signed in with Clerk"
      : "Sign in to save history"
    : token
      ? "Signed in"
      : APP_API_KEY
        ? "Development API key"
        : "Sign in required";

  const resultRef = useRef<HTMLDivElement | null>(null);
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const authDialogRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (messages.length || loading || error) {
      resultRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }
  }, [messages, loading, error]);

  useEffect(() => {
    if (!authOpen) return;

    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setAuthOpen(false);
      }
    }

    const focusTimer = window.setTimeout(() => {
      const target = authDialogRef.current?.querySelector<HTMLElement>(
        "input, .clerk-actions button, .auth-card-modal button"
      );
      target?.focus();
    }, 0);

    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [authOpen]);

  useEffect(() => {
    if (externalAuth?.enabled) {
      if (!externalAuth.isLoaded || !externalAuth.isSignedIn) {
        setConversations([]);
        return;
      }

      externalAuth
        .getToken()
        .then((authToken) => fetchConversations(authToken || ""))
        .then(setConversations)
        .catch(() => setConversations([]));
      return;
    }

    if (!token) {
      setConversations([]);
      return;
    }

    fetchConversations(token).then(setConversations).catch(() => setConversations([]));
  }, [token, externalAuth?.enabled, externalAuth?.isLoaded, externalAuth?.isSignedIn]);

  async function currentAuthToken() {
    if (externalAuth?.enabled) {
      return externalAuth.isSignedIn
        ? (await externalAuth.getToken()) || ""
        : "";
    }

    return token;
  }

  async function handleAuth(event: FormEvent) {
    event.preventDefault();
    setError("");

    try {
      const auth = await submitAuth(authMode, email.trim(), password, fullName.trim());
      setToken(auth.access_token || "");
      setUser(auth.user || null);
      localStorage.setItem("finintel_token", auth.access_token || "");
      localStorage.setItem("finintel_user", JSON.stringify(auth.user));
      setConversations(await fetchConversations(auth.access_token || ""));
      setPassword("");
      setAuthOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed.");
    }
  }

  function logout() {
    if (externalAuth?.enabled) {
      externalAuth.signOut().catch(() => undefined);
      setConversations([]);
      setCurrentConversationId("");
      setAuthOpen(false);
      return;
    }

    setToken("");
    setUser(null);
    localStorage.removeItem("finintel_token");
    localStorage.removeItem("finintel_user");
    setConversations([]);
    setCurrentConversationId("");
    setAuthOpen(false);
  }

  function selectExample(example: string) {
    setQuery(example);
    requestAnimationFrame(() => composerInputRef.current?.focus());
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();

    if (!trimmed) {
      setError("Enter a question to analyze.");
      return;
    }

    const authToken = await currentAuthToken();

    if (!authToken && !APP_API_KEY) {
      setError("Please login or configure a development API key before asking FinIntel.");
      setAuthOpen(true);
      return;
    }

    const context = messages;
    const effectiveAnswerDetail: AnswerDetail =
      workMode === "report" ? "detailed" : answerDetail;
    const submittedQuery = trimmed;

    setLoading(true);
    setError("");
    setProgressEvents([]);
    setQuery("");
    setMessages((current) => [
      ...current,
      {
        id: newMessageId("user"),
        role: "user",
        content: trimmed,
        mode: workMode,
      },
    ]);

    try {
      const data = await fetchAnalysisStream(
        submittedQuery,
        authToken,
        effectiveAnswerDetail,
        context,
        currentConversationId,
        workMode,
        (progress) => {
          setProgressEvents((current) => [
            ...current,
            progress,
          ]);
        }
      );
      if (!data.response?.success) {
        throw new Error(data.response?.error || data.error || "Analysis failed.");
      }
      if (data.conversation_id) {
        setCurrentConversationId(data.conversation_id);
      }
      setMessages((current) => [
        ...current,
        {
          id: newMessageId("assistant"),
          role: "assistant",
          result: data,
          mode: workMode,
        },
      ]);
      if (authToken) {
        setConversations(await fetchConversations(authToken));
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Unexpected error.";
      const readableMessage =
        message === "Failed to fetch"
          ? "Could not reach the backend. Check that FastAPI is running on port 8000 and that CORS includes the React dev server."
          : message;
      setError(readableMessage);
      setMessages((current) => [
        ...current,
        {
          id: newMessageId("error"),
          role: "error",
          content: readableMessage,
        },
      ]);
    } finally {
      setLoading(false);
      setProgressEvents([]);
    }
  }

  return (
    <main className="chat-app">
      <aside className="chat-sidebar">
        <div className="brand">
          <img src="/finintel-logo.png" alt="FinIntel AI logo" />
          <div>
            <strong>FinIntel AI</strong>
            <span>Indian Market Intelligence</span>
          </div>
        </div>

        <div className="sidebar-snapshot" aria-label="Session snapshot">
          <div>
            <span>Market</span>
            <strong>India equities</strong>
          </div>
          <div>
            <span>Depth</span>
            <strong>{workMode === "report" ? "Detailed" : answerDetail}</strong>
          </div>
        </div>

        <button
          className="new-chat-button"
          type="button"
          onClick={() => {
            setQuery("");
            setMessages([]);
            setError("");
            setCurrentConversationId("");
          }}
        >
          + New research chat
        </button>

        <section className="sidebar-section">
          <div className="sidebar-title">Mode</div>
          <div className="mode-switch">
            <button
              className={workMode === "chat" ? "active" : ""}
              type="button"
              aria-label="Chat"
              aria-pressed={workMode === "chat"}
              onClick={() => setWorkMode("chat")}
            >
              <span>Chat</span>
              <small>Focused answers</small>
            </button>
            <button
              className={workMode === "report" ? "active" : ""}
              type="button"
              aria-label="Generate report"
              aria-pressed={workMode === "report"}
              onClick={() => setWorkMode("report")}
            >
              <span>Generate report</span>
              <small>Export-ready brief</small>
            </button>
          </div>
        </section>

        <section className="sidebar-section">
          <div className="sidebar-title">
            {workMode === "report" ? "Report ideas" : "Try asking"}
          </div>
          <div className="example-list">
            {modeExamples.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => selectExample(example)}
                aria-label={`Use prompt: ${example}`}
              >
                {example}
              </button>
            ))}
          </div>
        </section>

        <section className="sidebar-section sidebar-history">
          <div className="sidebar-title">Recent chats</div>
          {displayedUser && conversations.length > 0 ? (
            conversations.map((item) => (
              <button
                key={item.conversation_id}
                className={
                  item.conversation_id === currentConversationId
                    ? "active"
                    : ""
                }
                type="button"
                aria-current={
                  item.conversation_id === currentConversationId
                    ? "true"
                    : undefined
                }
                onClick={async () => {
                  const authToken = await currentAuthToken();
                  const storedMessages = await fetchConversationMessages(
                    authToken,
                    item.conversation_id
                  );
                  setQuery("");
                  setError("");
                  setCurrentConversationId(
                    item.conversation_id
                  );
                  setMessages(
                    messagesFromStoredConversation(
                      storedMessages
                    )
                  );
                }}
              >
                <span>{formatHistoryDate(item.updated_at) || "Conversation"}</span>
                <strong>{item.title}</strong>
              </button>
            ))
          ) : (
            <div className="history-empty">
              <p>
                {displayedUser
                  ? "Your research chats will appear here."
                  : "Sign in to save your research history."}
              </p>
              {!displayedUser && (
                <button type="button" onClick={() => setAuthOpen(true)}>
                  Open account
                </button>
              )}
            </div>
          )}
        </section>
      </aside>

      <section className="chat-main">
        <header className="chat-topbar">
          <div className="topbar-heading">
            <p className="eyebrow">{modeCopy.eyebrow}</p>
            <h1 className="topbar-title">{modeCopy.title}</h1>
            {activeConversation && (
              <span className="active-conversation-label">
                {activeConversation.title}
              </span>
            )}
          </div>
          <div className="topbar-actions">
            <div className="topbar-context" aria-label="Current session">
              <span>{authStatus}</span>
              <span>{currentConversationId ? "Saved chat" : "New session"}</span>
            </div>
            <button
              className="nav-auth-button"
              type="button"
              onClick={() => setAuthOpen(true)}
              aria-label={
                displayedUser
                  ? `Open account menu for ${displayedUser.full_name}`
                  : "Open account sign in"
              }
            >
              <span className="nav-auth-icon" aria-hidden="true" />
              {displayedUser ? displayedUser.full_name : "Sign Up / Login"}
              <span className="nav-auth-caret" aria-hidden="true" />
            </button>
          </div>
        </header>

        <section className="chat-thread" aria-live="polite" aria-busy={loading}>
          {messages.length === 0 && !loading && !error && (
            <section className="welcome-panel">
              <span className="welcome-kicker">Market research workspace</span>
              <h2>How can I help with Indian markets today?</h2>
              <p>{modeCopy.welcome}</p>
              <div className="welcome-query-grid">
                {modeExamples.slice(0, 3).map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => selectExample(example)}
                  >
                    <span>{workMode === "report" ? "Report" : "Prompt"}</span>
                    <strong>{example}</strong>
                  </button>
                ))}
              </div>
              <TrustStrip />
            </section>
          )}

          {messages.map((message) =>
            message.role === "user" ? (
              <div
                className="message-row user-message"
                key={message.id}
                aria-label="Your message"
              >
                <div className="message-bubble">{message.content}</div>
              </div>
            ) : message.role === "assistant" ? (
              <div
                className={`message-row assistant-row ${
                  message.mode === "report" ? "assistant-row-wide" : ""
                }`}
                key={message.id}
              >
                <AssistantResultMessage
                  result={message.result}
                  fallbackDetail={answerDetail}
                  mode={message.mode}
                />
              </div>
            ) : (
              <div className="message-row assistant-row" key={message.id}>
                <div className="error-banner chat-error">{message.content}</div>
              </div>
            )
          )}

      {authOpen && (
        <div
          className="auth-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setAuthOpen(false);
            }
          }}
        >
          <section
            className="auth-modal"
            aria-modal="true"
            role="dialog"
            aria-labelledby="auth-modal-title"
            aria-describedby="auth-modal-copy"
            ref={authDialogRef}
          >
            <button
              className="auth-modal-close"
              type="button"
              aria-label="Close account dialog"
              onClick={() => setAuthOpen(false)}
            >
              <span aria-hidden="true">x</span>
            </button>
            <div className="auth-modal-copy">
              <span>FinIntel account</span>
              <h2 id="auth-modal-title">
                {displayedUser ? "Account details" : "Sign in to continue"}
              </h2>
              <p id="auth-modal-copy">
                Save chat history and keep your research questions tied to your account.
              </p>
            </div>

            <form className="auth-card auth-card-modal" onSubmit={handleAuth}>
              {externalAuth?.enabled ? (
                <>
                  {externalAuth.isLoaded && externalSignedIn ? (
                    <div className="account-summary">
                      <strong>{externalAuth.fullName}</strong>
                      <small>{externalAuth.email}</small>
                    </div>
                  ) : (
                    <small>Use your Clerk account to save history.</small>
                  )}
                  {externalAuth.controls}
                </>
              ) : user ? (
                <>
                  <div className="account-summary">
                    <strong>{user.full_name}</strong>
                    <small>{user.email}</small>
                  </div>
                  <button type="button" onClick={logout}>
                    Sign out
                  </button>
                </>
              ) : (
                <>
                  <div className="auth-tabs">
                    <button
                      className={authMode === "login" ? "active" : ""}
                      type="button"
                      onClick={() => setAuthMode("login")}
                    >
                      Login
                    </button>
                    <button
                      className={authMode === "register" ? "active" : ""}
                      type="button"
                      onClick={() => setAuthMode("register")}
                    >
                      Register
                    </button>
                  </div>
                  {authMode === "register" && (
                    <>
                      <label className="sr-only" htmlFor="auth-full-name">
                        Full name
                      </label>
                      <input
                        id="auth-full-name"
                        value={fullName}
                        onChange={(event) => setFullName(event.target.value)}
                        placeholder="Full name"
                        autoComplete="name"
                      />
                    </>
                  )}
                  <label className="sr-only" htmlFor="auth-email">
                    Email
                  </label>
                  <input
                    id="auth-email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="Email"
                    type="email"
                    autoComplete="email"
                  />
                  <label className="sr-only" htmlFor="auth-password">
                    Password
                  </label>
                  <input
                    id="auth-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Password"
                    type="password"
                    autoComplete={authMode === "login" ? "current-password" : "new-password"}
                  />
                  <button type="submit">
                    {authMode === "login" ? "Login" : "Create account"}
                  </button>
                </>
              )}
            </form>
          </section>
        </div>
      )}

      <div ref={resultRef}>
        {error && messages.length === 0 && (
          <div className="error-banner error-banner-action" role="alert">
            <span>{error}</span>
            {!displayedUser && (
              <button type="button" onClick={() => setAuthOpen(true)}>
                Open account
              </button>
            )}
          </div>
        )}
      </div>

      {loading && (
        <section className="loading-card progress-card" role="status">
          <div className="spinner" />
          <div>
            <strong>Analyzing market context</strong>
            <span>
              {progressEvents[progressEvents.length - 1]?.step
                || modeCopy.loading}
            </span>
            <div
              className="progress-meter"
              aria-hidden="true"
            >
              <span style={{ width: `${progressValue}%` }} />
            </div>
            {progressEvents.length > 0 && (
              <ol className="progress-steps">
                {progressEvents.map((progress) => (
                  <li key={`${progress.index}-${progress.step}`}>
                    {progress.step}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
      )}

        </section>

        <form className="chat-composer" onSubmit={submit}>
          <div className="composer-toolbar">
            <span id="composer-status">{authStatus}</span>
            <div className="composer-actions">
              <div className="mode-switch mode-switch-inline" aria-label="Work mode">
                <button
                  className={workMode === "chat" ? "active" : ""}
                  type="button"
                  aria-pressed={workMode === "chat"}
                  onClick={() => setWorkMode("chat")}
                >
                  Chat
                </button>
                <button
                  className={workMode === "report" ? "active" : ""}
                  type="button"
                  aria-pressed={workMode === "report"}
                  onClick={() => setWorkMode("report")}
                >
                  Report
                </button>
              </div>
              <div className="detail-toggle" aria-label="Answer detail">
                <button
                  className={workMode === "chat" && answerDetail === "brief" ? "active" : ""}
                  type="button"
                  aria-pressed={workMode === "chat" && answerDetail === "brief"}
                  onClick={() => setAnswerDetail("brief")}
                  disabled={workMode === "report"}
                >
                  Brief
                </button>
                <button
                  className={workMode === "report" || answerDetail === "detailed" ? "active" : ""}
                  type="button"
                  aria-pressed={workMode === "report" || answerDetail === "detailed"}
                  onClick={() => setAnswerDetail("detailed")}
                >
                  Detailed
                </button>
              </div>
            </div>
          </div>
          <label className="sr-only" htmlFor="query">Ask FinIntel</label>
          <div className="composer-input-row">
            <textarea
              id="query"
              ref={composerInputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={modeCopy.placeholder}
              aria-describedby="composer-status"
              rows={2}
            />
            <button disabled={loading || !query.trim()} type="submit">
              {loading ? "Analyzing..." : modeCopy.submit}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
