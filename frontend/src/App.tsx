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

const ROUTE_LABELS: Record<string, string> = {
  PRICE_QUERY: "Price Check",
  EDUCATIONAL: "Learning",
  DISCOVERY: "Discovery",
  NEWS: "News",
  COMPARISON: "Comparison",
  FUNDAMENTAL: "Fundamentals",
};

type Route =
  | "PRICE_QUERY"
  | "EDUCATIONAL"
  | "DISCOVERY"
  | "NEWS"
  | "COMPARISON"
  | "FUNDAMENTAL"
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
    }
  | {
      id: string;
      role: "assistant";
      result: ApiResult;
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
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numeric);
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

function getPayloadTitle(route: Route, payload: Record<string, unknown>) {
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
  if (route === "PRICE_QUERY") return payload.message;
  if (route === "EDUCATIONAL") return payload.simple_definition;
  if (route === "DISCOVERY") return payload.summary;
  if (route === "NEWS") return payload.headline_summary;
  if (route === "COMPARISON") return payload.summary;
  return payload.overall_view || payload.business_overview;
}

async function fetchAnalysis(
  query: string,
  token: string,
  answerDetail: AnswerDetail,
  conversationContext: ChatMessage[],
  conversationId: string
): Promise<ApiResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    headers["X-API-Key"] = APP_API_KEY;
  }

  const response = await fetch(`${BACKEND_API_URL}/chat`, {
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

  const response = await fetch(`${BACKEND_API_URL}/chat/stream`, {
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
      conversationId
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

function Sources({ sources }: { sources: unknown }) {
  const list = asList(sources);
  if (!list.length) return null;

  return (
    <section className="section">
      <h3>Sources</h3>
      <div className="source-grid">
        {list.map((source) => (
          <a href={source} target="_blank" rel="noreferrer" key={source}>
            {source.replace(/^https?:\/\/(www\.)?/, "")}
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
      <span>Sources</span>
      <span>Live prices</span>
      <span>Comparisons</span>
      <span>History</span>
    </div>
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

function AssistantResultMessage({
  result,
  fallbackDetail,
}: {
  result: ApiResult;
  fallbackDetail: AnswerDetail;
}) {
  const payload = result.response?.data || {};
  const score = getConfidenceScore(payload, result);
  const sourceCount = asList(payload.sources_used || payload.sources).length;

  return (
    <section className="result-shell assistant-message">
      <div className="summary-grid">
        <section className="summary-card">
          <div className="summary-topline">
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
            <StatPill label="Sources" value={sourceCount ? sourceCount : "Not provided"} />
            <StatPill label="Routing confidence" value={formatPercent(result.routing?.confidence)} />
          </div>
        </section>

        <section className="confidence-card">
          <span>Confidence</span>
          <strong>{Math.round(score * 100)}%</strong>
          <small>{confidenceLabel(score)}</small>
          <div className="meter">
            <div style={{ width: `${Math.round(score * 100)}%` }} />
          </div>
        </section>
      </div>

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

  const resultRef = useRef<HTMLDivElement | null>(null);

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

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setAuthOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);

    return () => window.removeEventListener("keydown", closeOnEscape);
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
      return;
    }

    const context = messages;

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
      },
    ]);

    try {
      const data = await fetchAnalysisStream(
        trimmed,
        authToken,
        answerDetail,
        context,
        currentConversationId,
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
          New research chat
        </button>

        <section className="sidebar-section">
          <div className="sidebar-title">Try asking</div>
          <div className="example-list">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuery(example)}
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
                type="button"
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
                <span>Conversation</span>
                <strong>{item.title}</strong>
              </button>
            ))
          ) : (
            <p className="history-empty">
              {displayedUser
                ? "Your research chats will appear here."
                : "Sign in to save your research history."}
            </p>
          )}
        </section>
      </aside>

      <section className="chat-main">
        <header className="chat-topbar">
          <div>
            <p className="eyebrow">AI equity research, grounded with sources</p>
            <strong className="topbar-title">Research chat</strong>
          </div>
          <button
            className="nav-auth-button"
            type="button"
            onClick={() => setAuthOpen(true)}
          >
            <span className="nav-auth-icon" aria-hidden="true" />
            {displayedUser ? displayedUser.full_name : "Sign Up / Login"}
            <span aria-hidden="true">v</span>
          </button>
        </header>

        <section className="chat-thread">
          {messages.length === 0 && !loading && !error && (
            <section className="welcome-panel">
              <h2>How can I help with Indian markets today?</h2>
              <p>
                Ask about prices, ratios, company fundamentals, comparisons,
                discovery screens, or news context.
              </p>
              <TrustStrip />
            </section>
          )}

          {messages.map((message) =>
            message.role === "user" ? (
              <div className="message-row user-message" key={message.id}>
                <div className="message-bubble">{message.content}</div>
              </div>
            ) : message.role === "assistant" ? (
              <div className="message-row assistant-row" key={message.id}>
                <AssistantResultMessage
                  result={message.result}
                  fallbackDetail={answerDetail}
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
          >
            <button
              className="auth-modal-close"
              type="button"
              aria-label="Close account dialog"
              onClick={() => setAuthOpen(false)}
            >
              x
            </button>
            <div className="auth-modal-copy">
              <span>FinIntel account</span>
              <h2 id="auth-modal-title">
                {displayedUser ? "Account details" : "Sign in to continue"}
              </h2>
              <p>
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
                    <input
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                      placeholder="Full name"
                    />
                  )}
                  <input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="Email"
                    type="email"
                  />
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Password"
                    type="password"
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
        {error && messages.length === 0 && <div className="error-banner">{error}</div>}
      </div>

      {loading && (
        <section className="loading-card progress-card">
          <div className="spinner" />
          <div>
            <strong>Analyzing market context</strong>
            <span>
              {progressEvents[progressEvents.length - 1]?.step
                || "Routing, retrieving sources, and preparing a grounded answer."}
            </span>
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
            <span>
              {externalAuth?.enabled
                ? externalSignedIn
                  ? "Clerk account"
                  : "Clerk login"
                : token
                  ? "Account mode"
                  : APP_API_KEY
                    ? "Dev key mode"
                    : "Login required"}
            </span>
            <div className="detail-toggle" aria-label="Answer detail">
              <button
                className={answerDetail === "brief" ? "active" : ""}
                type="button"
                onClick={() => setAnswerDetail("brief")}
              >
                Brief
              </button>
              <button
                className={answerDetail === "detailed" ? "active" : ""}
                type="button"
                onClick={() => setAnswerDetail("detailed")}
              >
                Detailed
              </button>
            </div>
          </div>
          <label className="sr-only" htmlFor="query">Ask FinIntel</label>
          <div className="composer-input-row">
            <textarea
              id="query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask about HDFC Bank, ROE, IT stocks, or latest market news"
              rows={2}
            />
            <button disabled={loading || !query.trim()} type="submit">
              {loading ? "..." : "Analyze"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
