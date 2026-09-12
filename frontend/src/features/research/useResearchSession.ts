import { useCallback, useState } from "react";
import type {
  AnswerDetail,
  ChatMessage,
  ProgressEvent,
  WorkMode,
} from "./types";

function progressPercent(events: ProgressEvent[]) {
  const latest = events[events.length - 1];

  if (latest?.total && latest.total > 0) {
    return Math.min(
      96,
      Math.max(16, Math.round((latest.index / latest.total) * 100))
    );
  }

  return events.length ? 52 : 16;
}

export function useResearchSession() {
  const [queryDrafts, setQueryDrafts] = useState<Record<WorkMode, string>>({
    chat: "",
    report: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [answerDetail, setAnswerDetail] = useState<AnswerDetail>("brief");
  const [workMode, setWorkMode] = useState<WorkMode>("chat");

  const setActiveQuery = useCallback((value: string) => {
    setQueryDrafts((current) => ({
      ...current,
      [workMode]: value,
    }));
  }, [workMode]);

  const clearQueryDrafts = useCallback(() => {
    setQueryDrafts({ chat: "", report: "" });
  }, []);

  return {
    answerDetail,
    clearQueryDrafts,
    error,
    loading,
    messages,
    progressEvents,
    progressValue: progressPercent(progressEvents),
    query: queryDrafts[workMode],
    setActiveQuery,
    setAnswerDetail,
    setError,
    setLoading,
    setMessages,
    setProgressEvents,
    setWorkMode,
    workMode,
  };
}
