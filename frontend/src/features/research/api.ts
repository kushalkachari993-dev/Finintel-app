import type {
  AnswerDetail,
  ApiResult,
  ChatMessage,
  ConversationPage,
  ProgressEvent,
  StoredConversationMessage,
  WorkMode,
} from "./types";

const BACKEND_API_URL =
  import.meta.env.VITE_BACKEND_API_URL || "http://127.0.0.1:8000";

function messageContextContent(message: ChatMessage) {
  if (message.role !== "assistant") {
    return message.content;
  }

  const response = message.result.response;
  const value = response?.data ?? response?.error;

  if (typeof value === "string") {
    return value.slice(0, 2000);
  }

  if (value) {
    return JSON.stringify(value).slice(0, 2000);
  }

  return message.result.query;
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

  headers.Authorization = `Bearer ${token}`;

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
          content: messageContextContent(message),
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

  headers.Authorization = `Bearer ${token}`;

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
          content: messageContextContent(message),
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

async function fetchConversations(
  token: string,
  {
    limit = 30,
    offset = 0,
    search = "",
  }: {
    limit?: number;
    offset?: number;
    search?: string;
  } = {}
): Promise<ConversationPage> {
  if (!token) return { conversations: [], hasMore: false };

  const parameters = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (search.trim()) {
    parameters.set("search", search.trim());
  }

  const response = await fetch(`${BACKEND_API_URL}/chat/conversations?${parameters}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !body?.success) {
    return { conversations: [], hasMore: false };
  }

  return {
    conversations: body.conversations || [],
    hasMore: Boolean(body.has_more),
  };
}

async function updateConversation(
  token: string,
  conversationId: string,
  update: { title?: string; pinned?: boolean }
) {
  const response = await fetch(`${BACKEND_API_URL}/chat/conversations/${conversationId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(update),
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !body?.success) {
    throw new Error(body?.error || "Could not update conversation.");
  }
}

async function deleteConversation(
  token: string,
  conversationId: string
) {
  const response = await fetch(`${BACKEND_API_URL}/chat/conversations/${conversationId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok || !body?.success) {
    throw new Error(body?.error || "Could not delete conversation.");
  }
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

export {
  deleteConversation,
  fetchAnalysisStream,
  fetchConversationMessages,
  fetchConversations,
  updateConversation,
};
