import type { FormEvent, RefObject } from "react";
import type {
  AnswerDetail,
  ConversationSummary,
  DisplayedUser,
  WorkMode,
} from "../types";

type ConversationGroup = {
  label: string;
  items: ConversationSummary[];
};

type ResearchSidebarProps = {
  answerDetail: AnswerDetail;
  conversationGroups: ConversationGroup[];
  conversations: ConversationSummary[];
  currentConversationId: string;
  deleteConfirmationId: string;
  displayedUser: DisplayedUser;
  examples: string[];
  hasActivity: boolean;
  historyHasMore: boolean;
  historyLoading: boolean;
  historyMenuId: string;
  historySearch: string;
  inert: boolean;
  mobileNavCloseRef: RefObject<HTMLButtonElement | null>;
  mobileNavOpen: boolean;
  renameDraft: string;
  renamingConversationId: string;
  workMode: WorkMode;
  onCancelDelete: () => void;
  onCancelRename: () => void;
  onClose: () => void;
  onHistoryMenuToggle: (conversationId: string) => void;
  onHistorySearchChange: (search: string) => void;
  onLoadMore: () => void;
  onModeChange: (mode: WorkMode) => void;
  onNewChat: () => void;
  onOpenAccount: () => void;
  onOpenConversation: (item: ConversationSummary) => void;
  onRemoveConversation: (item: ConversationSummary) => void;
  onRenameDraftChange: (title: string) => void;
  onRenameStart: (item: ConversationSummary) => void;
  onRenameSubmit: (conversationId: string) => void;
  onSelectExample: (example: string) => void;
  onTogglePin: (item: ConversationSummary) => void;
};

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

export function ResearchSidebar({
  answerDetail,
  conversationGroups,
  conversations,
  currentConversationId,
  deleteConfirmationId,
  displayedUser,
  examples,
  hasActivity,
  historyHasMore,
  historyLoading,
  historyMenuId,
  historySearch,
  inert,
  mobileNavCloseRef,
  mobileNavOpen,
  renameDraft,
  renamingConversationId,
  workMode,
  onCancelDelete,
  onCancelRename,
  onClose,
  onHistoryMenuToggle,
  onHistorySearchChange,
  onLoadMore,
  onModeChange,
  onNewChat,
  onOpenAccount,
  onOpenConversation,
  onRemoveConversation,
  onRenameDraftChange,
  onRenameStart,
  onRenameSubmit,
  onSelectExample,
  onTogglePin,
}: ResearchSidebarProps) {
  function submitRename(event: FormEvent, conversationId: string) {
    event.preventDefault();
    onRenameSubmit(conversationId);
  }

  return (
    <aside
      className={`chat-sidebar ${mobileNavOpen ? "mobile-nav-open" : ""}`}
      id="research-navigation"
      aria-label="Research navigation"
      inert={inert ? true : undefined}
    >
      <div className="sidebar-header">
        <div className="brand">
          <span className="brand-mark">
            <img src="/finintel-logo.png" alt="FinIntel AI logo" />
          </span>
          <div>
            <strong>FinIntel AI</strong>
            <span>Indian Market Intelligence</span>
          </div>
        </div>

        <button
          className="sidebar-close-button"
          type="button"
          aria-label="Close research navigation"
          onClick={onClose}
          ref={mobileNavCloseRef}
        >
          <span aria-hidden="true">x</span>
        </button>
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

      <button className="new-chat-button" type="button" onClick={onNewChat}>
        <span aria-hidden="true">+</span>
        New research chat
      </button>

      <section className="sidebar-section">
        <div className="sidebar-title">Mode</div>
        <div className="mode-switch">
          <button
            className={workMode === "chat" ? "active" : ""}
            type="button"
            aria-label="Chat"
            aria-pressed={workMode === "chat"}
            onClick={() => onModeChange("chat")}
          >
            <span>Chat</span>
            <small>Focused answers</small>
          </button>
          <button
            className={workMode === "report" ? "active" : ""}
            type="button"
            aria-label="Generate report"
            aria-pressed={workMode === "report"}
            onClick={() => onModeChange("report")}
          >
            <span>Generate report</span>
            <small>Export-ready brief</small>
          </button>
        </div>
      </section>

      {hasActivity && (
        <section className="sidebar-section">
          <div className="sidebar-title">
            {workMode === "report" ? "Report ideas" : "Try asking"}
          </div>
          <div className="example-list">
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => onSelectExample(example)}
                aria-label={`Use prompt: ${example}`}
              >
                {example}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="sidebar-section sidebar-history">
        <div className="sidebar-title-row">
          <div className="sidebar-title">Research history</div>
          {displayedUser && <span>{conversations.length}</span>}
        </div>
        {displayedUser && (
          <label className="history-search">
            <span className="sr-only">Search conversations</span>
            <input
              type="search"
              value={historySearch}
              onChange={(event) => onHistorySearchChange(event.target.value)}
              placeholder="Search research"
              autoComplete="off"
            />
          </label>
        )}
        {displayedUser && conversations.length > 0 ? (
          <>
            {conversationGroups.map((group) => (
              <div className="history-group" key={group.label}>
                <div className="history-group-label">{group.label}</div>
                {group.items.map((item) => (
                  <article
                    className={`history-item ${item.conversation_id === currentConversationId ? "active" : ""}`}
                    key={item.conversation_id}
                  >
                    {renamingConversationId === item.conversation_id ? (
                      <form
                        className="history-rename-form"
                        onSubmit={(event) => submitRename(event, item.conversation_id)}
                      >
                        <input
                          value={renameDraft}
                          onChange={(event) => onRenameDraftChange(event.target.value)}
                          aria-label="Conversation title"
                          maxLength={120}
                          autoFocus
                        />
                        <div>
                          <button type="submit" disabled={!renameDraft.trim()}>
                            Save
                          </button>
                          <button type="button" onClick={onCancelRename}>
                            Cancel
                          </button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <button
                          className="history-open-button"
                          type="button"
                          aria-current={
                            item.conversation_id === currentConversationId
                              ? "true"
                              : undefined
                          }
                          onClick={() => onOpenConversation(item)}
                        >
                          <span>{formatHistoryDate(item.updated_at) || "Conversation"}</span>
                          <strong>{item.title}</strong>
                        </button>
                        <button
                          className="history-menu-button"
                          type="button"
                          aria-label={`Actions for ${item.title}`}
                          aria-expanded={historyMenuId === item.conversation_id}
                          onClick={() => onHistoryMenuToggle(item.conversation_id)}
                        >
                          <span aria-hidden="true">...</span>
                        </button>
                        {historyMenuId === item.conversation_id && (
                          <div className="history-actions" role="menu">
                            <button
                              type="button"
                              role="menuitem"
                              onClick={() => onTogglePin(item)}
                            >
                              {item.pinned ? "Unpin" : "Pin to top"}
                            </button>
                            <button
                              type="button"
                              role="menuitem"
                              onClick={() => onRenameStart(item)}
                            >
                              Rename
                            </button>
                            <button
                              className="history-delete-button"
                              type="button"
                              role="menuitem"
                              onClick={() => onRemoveConversation(item)}
                            >
                              {deleteConfirmationId === item.conversation_id
                                ? "Confirm delete"
                                : "Delete"}
                            </button>
                            {deleteConfirmationId === item.conversation_id && (
                              <button type="button" role="menuitem" onClick={onCancelDelete}>
                                Cancel
                              </button>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </article>
                ))}
              </div>
            ))}
            {historyHasMore && (
              <button
                className="history-load-more"
                type="button"
                onClick={onLoadMore}
                disabled={historyLoading}
              >
                {historyLoading ? "Loading..." : "Load more"}
              </button>
            )}
          </>
        ) : (
          <div className="history-empty">
            <p>
              {displayedUser
                ? historyLoading
                  ? "Loading research history..."
                  : historySearch
                    ? "No research matches this search."
                    : "Your research chats will appear here."
                : "Sign in to save your research history."}
            </p>
            {!displayedUser && (
              <button type="button" onClick={onOpenAccount}>
                Open account
              </button>
            )}
          </div>
        )}
      </section>
    </aside>
  );
}
