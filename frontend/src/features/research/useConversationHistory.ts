import { useDeferredValue, useMemo, useState } from "react";
import type { ConversationSummary } from "./types";

function conversationDateGroup(value: number) {
  const timestamp = value > 10_000_000_000 ? value : value * 1000;
  const date = new Date(timestamp);
  const today = new Date();
  const startOfToday = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate()
  ).getTime();
  const startOfDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate()
  ).getTime();
  const dayDifference = Math.floor((startOfToday - startOfDay) / 86_400_000);

  if (dayDifference <= 0) return "Today";
  if (dayDifference === 1) return "Yesterday";
  if (dayDifference < 7) return "Previous 7 days";
  return "Older";
}

export function useConversationHistory() {
  const [currentConversationId, setCurrentConversationId] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [historySearch, setHistorySearch] = useState("");
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMenuId, setHistoryMenuId] = useState("");
  const [renamingConversationId, setRenamingConversationId] = useState("");
  const [renameDraft, setRenameDraft] = useState("");
  const [deleteConfirmationId, setDeleteConfirmationId] = useState("");
  const deferredHistorySearch = useDeferredValue(historySearch);

  const activeConversation = conversations.find(
    (item) => item.conversation_id === currentConversationId
  );
  const conversationGroups = useMemo(() => {
    const groups = new Map<string, ConversationSummary[]>();

    conversations.forEach((conversation) => {
      const label = conversation.pinned
        ? "Pinned"
        : conversationDateGroup(conversation.updated_at);
      groups.set(label, [...(groups.get(label) || []), conversation]);
    });

    return ["Pinned", "Today", "Yesterday", "Previous 7 days", "Older"]
      .map((label) => ({
        label,
        items: [...(groups.get(label) || [])].sort(
          (left, right) => right.updated_at - left.updated_at
        ),
      }))
      .filter((group) => group.items.length > 0);
  }, [conversations]);

  return {
    activeConversation,
    conversationGroups,
    conversations,
    currentConversationId,
    deferredHistorySearch,
    deleteConfirmationId,
    historyHasMore,
    historyLoading,
    historyMenuId,
    historySearch,
    renameDraft,
    renamingConversationId,
    setConversations,
    setCurrentConversationId,
    setDeleteConfirmationId,
    setHistoryHasMore,
    setHistoryLoading,
    setHistoryMenuId,
    setHistorySearch,
    setRenameDraft,
    setRenamingConversationId,
  };
}
