import type { ReactNode } from "react";

export type AnswerDetail = "brief" | "detailed";

export type WorkMode = "chat" | "report";

export type Route =
  | "PRICE_QUERY"
  | "EDUCATIONAL"
  | "DISCOVERY"
  | "NEWS"
  | "COMPARISON"
  | "FUNDAMENTAL"
  | "REPORT"
  | string;

export type ApiResult = {
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

export type ModeCopy = {
  eyebrow: string;
  title: string;
  welcome: string;
  placeholder: string;
  loading: string;
  submit: string;
};

export type ExternalAuth = {
  isLoaded: boolean;
  isSignedIn: boolean;
  email: string;
  fullName: string;
  getToken: () => Promise<string | null>;
  controls: ReactNode;
};

export type DisplayedUser = {
  full_name: string;
  email: string;
} | null;

export type ConversationSummary = {
  conversation_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  pinned?: boolean;
};

export type ProgressEvent = {
  step: string;
  index: number;
  total: number;
};

export type ConversationPage = {
  conversations: ConversationSummary[];
  hasMore: boolean;
};

export type StoredConversationMessage = {
  id: number;
  conversation_id: string;
  role: "user" | "assistant" | "error";
  content: string;
  payload?: ApiResult | null;
  created_at: number;
};

export type ChatMessage =
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
