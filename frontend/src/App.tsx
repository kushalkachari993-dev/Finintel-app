import {
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  AccountDialog,
  AssistantResultMessage,
  EXAMPLES,
  MODE_COPY,
  REPORT_EXAMPLES,
  ResearchComposer,
  ResearchSidebar,
  WelcomePanel,
  WorkspaceHeader,
  deleteConversation,
  fetchAnalysisStream,
  fetchConversationMessages,
  fetchConversations,
  updateConversation,
  useAccountDialog,
  useConversationHistory,
  useResearchSession,
  type AnswerDetail,
  type ApiResult,
  type ChatMessage,
  type ConversationSummary,
  type ExternalAuth,
  type StoredConversationMessage,
} from "./features/research";


function newMessageId(role: ChatMessage["role"]) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${role}-${crypto.randomUUID()}`;
  }

  return `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
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




export default function App({
  externalAuth,
}: {
  externalAuth: ExternalAuth;
}) {
  const {
    answerDetail,
    clearQueryDrafts,
    error,
    loading,
    messages,
    progressEvents,
    progressValue,
    query,
    setActiveQuery,
    setAnswerDetail,
    setError,
    setLoading,
    setMessages,
    setProgressEvents,
    setWorkMode,
    workMode,
  } = useResearchSession();
  const {
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
  } = useConversationHistory();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const externalSignedIn = Boolean(externalAuth.isSignedIn);
  const displayedUser = externalSignedIn
    ? {
        full_name: externalAuth.fullName,
        email: externalAuth.email,
      }
    : null;
  const modeCopy = MODE_COPY[workMode];
  const modeExamples = workMode === "report" ? REPORT_EXAMPLES : EXAMPLES;
  const authStatus = externalSignedIn
    ? "Signed in with Clerk"
    : "Sign in required";
  const mobileAuthLabel = displayedUser
    ? displayedUser.full_name.split(" ")[0]
    : "Sign in";

  const resultRef = useRef<HTMLDivElement | null>(null);
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const mobileNavToggleRef = useRef<HTMLButtonElement | null>(null);
  const mobileNavCloseRef = useRef<HTMLButtonElement | null>(null);
  const {
    close: closeAuthDialog,
    dialogRef: authDialogRef,
    isOpen: authOpen,
    open: openAuthDialog,
  } = useAccountDialog();

  useEffect(() => {
    if (messages.length || loading || error) {
      resultRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }
  }, [messages, loading, error]);

  useEffect(() => {
    if (!mobileNavOpen) return;

    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTimer = window.setTimeout(() => {
      mobileNavCloseRef.current?.focus();
    }, 240);

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !authDialogRef.current) {
        setMobileNavOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", closeOnEscape);

      if (
        document
          .getElementById("research-navigation")
          ?.contains(document.activeElement)
      ) {
        mobileNavToggleRef.current?.focus();
      }
    };
  }, [mobileNavOpen]);

  useEffect(() => {
    const desktopLayout = window.matchMedia("(min-width: 881px)");

    function closeDrawerOnDesktop() {
      if (desktopLayout.matches) {
        setMobileNavOpen(false);
      }
    }

    desktopLayout.addEventListener("change", closeDrawerOnDesktop);

    return () => {
      desktopLayout.removeEventListener("change", closeDrawerOnDesktop);
    };
  }, []);

  useEffect(() => {
    if (!historyMenuId) return;

    function closeHistoryMenu(event: KeyboardEvent | PointerEvent) {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;

      const target = event.target;
      if (
        event instanceof PointerEvent
        && target instanceof Element
        && target.closest(".history-actions, .history-menu-button")
      ) {
        return;
      }

      setHistoryMenuId("");
      setDeleteConfirmationId("");
    }

    window.addEventListener("keydown", closeHistoryMenu);
    window.addEventListener("pointerdown", closeHistoryMenu);

    return () => {
      window.removeEventListener("keydown", closeHistoryMenu);
      window.removeEventListener("pointerdown", closeHistoryMenu);
    };
  }, [historyMenuId]);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;

    if (!externalAuth.isLoaded || !externalAuth.isSignedIn) {
      setConversations([]);
      setHistoryHasMore(false);
      return;
    }

    timer = window.setTimeout(async () => {
      setHistoryLoading(true);

      try {
        const authToken = (await externalAuth.getToken()) || "";
        const page = await fetchConversations(authToken, {
          search: deferredHistorySearch,
        });

        if (!cancelled) {
          setConversations(page.conversations);
          setHistoryHasMore(page.hasMore);
        }
      } catch {
        if (!cancelled) {
          setConversations([]);
          setHistoryHasMore(false);
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      }
    }, deferredHistorySearch ? 180 : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    deferredHistorySearch,
    externalAuth.isLoaded,
    externalAuth.isSignedIn,
  ]);

  async function currentAuthToken() {
    return externalAuth.isSignedIn
      ? (await externalAuth.getToken()) || ""
      : "";
  }

  function selectExample(example: string) {
    setActiveQuery(example);
    setMobileNavOpen(false);
    requestAnimationFrame(() => composerInputRef.current?.focus());
  }

  async function openConversation(item: ConversationSummary) {
    const authToken = await currentAuthToken();
    const storedMessages = await fetchConversationMessages(
      authToken,
      item.conversation_id
    );
    clearQueryDrafts();
    setError("");
    setCurrentConversationId(item.conversation_id);
    setMessages(messagesFromStoredConversation(storedMessages));
    setHistoryMenuId("");
    setMobileNavOpen(false);
  }

  async function loadMoreConversations() {
    const authToken = await currentAuthToken();
    if (!authToken || historyLoading) return;

    setHistoryLoading(true);

    try {
      const page = await fetchConversations(authToken, {
        offset: conversations.length,
        search: deferredHistorySearch,
      });
      setConversations((current) => {
        const existing = new Set(current.map((item) => item.conversation_id));
        return [
          ...current,
          ...page.conversations.filter((item) => !existing.has(item.conversation_id)),
        ];
      });
      setHistoryHasMore(page.hasMore);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load more conversations.");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function saveConversationRename(conversationId: string) {
    const cleanTitle = renameDraft.trim();
    if (!cleanTitle) return;

    try {
      const authToken = await currentAuthToken();
      await updateConversation(authToken, conversationId, {
        title: cleanTitle,
      });
      setConversations((current) => current.map((item) =>
        item.conversation_id === conversationId
          ? { ...item, title: cleanTitle, updated_at: Math.floor(Date.now() / 1000) }
          : item
      ));
      setRenamingConversationId("");
      setHistoryMenuId("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not rename conversation.");
    }
  }

  async function toggleConversationPin(item: ConversationSummary) {
    try {
      const authToken = await currentAuthToken();
      const pinned = !item.pinned;
      await updateConversation(authToken, item.conversation_id, { pinned });
      setConversations((current) => current.map((conversation) =>
        conversation.conversation_id === item.conversation_id
          ? { ...conversation, pinned }
          : conversation
      ));
      setHistoryMenuId("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not organize conversation.");
    }
  }

  async function removeConversation(item: ConversationSummary) {
    if (deleteConfirmationId !== item.conversation_id) {
      setDeleteConfirmationId(item.conversation_id);
      return;
    }

    try {
      const authToken = await currentAuthToken();
      await deleteConversation(authToken, item.conversation_id);
      setConversations((current) => current.filter(
        (conversation) => conversation.conversation_id !== item.conversation_id
      ));
      if (currentConversationId === item.conversation_id) {
        setCurrentConversationId("");
        setMessages([]);
      }
      setDeleteConfirmationId("");
      setHistoryMenuId("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete conversation.");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();

    if (!trimmed) {
      setError("Enter a question to analyze.");
      return;
    }

    const authToken = await currentAuthToken();

    if (!authToken) {
      setError("Please sign in with Clerk before asking FinIntel.");
      openAuthDialog();
      return;
    }

    const context = messages;
    const effectiveAnswerDetail: AnswerDetail =
      workMode === "report" ? "detailed" : answerDetail;
    const submittedQuery = trimmed;

    setLoading(true);
    setError("");
    setProgressEvents([]);
    setActiveQuery("");
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
        const page = await fetchConversations(authToken, {
          search: deferredHistorySearch,
        });
        setConversations(page.conversations);
        setHistoryHasMore(page.hasMore);
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
      {mobileNavOpen && (
        <button
          className="mobile-nav-backdrop"
          type="button"
          aria-label="Close research navigation"
          inert={authOpen ? true : undefined}
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <ResearchSidebar
        answerDetail={answerDetail}
        conversationGroups={conversationGroups}
        conversations={conversations}
        currentConversationId={currentConversationId}
        deleteConfirmationId={deleteConfirmationId}
        displayedUser={displayedUser}
        examples={modeExamples}
        hasActivity={messages.length > 0 || loading || Boolean(error)}
        historyHasMore={historyHasMore}
        historyLoading={historyLoading}
        historyMenuId={historyMenuId}
        historySearch={historySearch}
        inert={authOpen}
        mobileNavCloseRef={mobileNavCloseRef}
        mobileNavOpen={mobileNavOpen}
        renameDraft={renameDraft}
        renamingConversationId={renamingConversationId}
        workMode={workMode}
        onCancelDelete={() => setDeleteConfirmationId("")}
        onCancelRename={() => setRenamingConversationId("")}
        onClose={() => setMobileNavOpen(false)}
        onHistoryMenuToggle={(conversationId) => {
          setHistoryMenuId((current) =>
            current === conversationId ? "" : conversationId
          );
          setDeleteConfirmationId("");
        }}
        onHistorySearchChange={setHistorySearch}
        onLoadMore={loadMoreConversations}
        onModeChange={(mode) => {
          setWorkMode(mode);
          setMobileNavOpen(false);
        }}
        onNewChat={() => {
          clearQueryDrafts();
          setMessages([]);
          setError("");
          setCurrentConversationId("");
          setMobileNavOpen(false);
        }}
        onOpenAccount={openAuthDialog}
        onOpenConversation={openConversation}
        onRemoveConversation={removeConversation}
        onRenameDraftChange={setRenameDraft}
        onRenameStart={(item) => {
          setRenameDraft(item.title);
          setRenamingConversationId(item.conversation_id);
          setHistoryMenuId("");
        }}
        onRenameSubmit={saveConversationRename}
        onSelectExample={selectExample}
        onTogglePin={toggleConversationPin}
      />

      <section
        className="chat-main"
        inert={mobileNavOpen || authOpen ? true : undefined}
      >
        <WorkspaceHeader
          activeConversationTitle={activeConversation?.title}
          authStatus={authStatus}
          currentConversationId={currentConversationId}
          displayedUser={displayedUser}
          mobileAuthLabel={mobileAuthLabel}
          mobileNavOpen={mobileNavOpen}
          mobileNavToggleRef={mobileNavToggleRef}
          modeCopy={modeCopy}
          onOpenAccount={openAuthDialog}
          onOpenMobileNav={() => setMobileNavOpen(true)}
        />

        <section
          className={`chat-thread ${messages.length === 0 && !loading && !error ? "chat-thread-empty" : ""}`}
          aria-live="polite"
          aria-busy={loading}
        >
          {messages.length === 0 && !loading && !error && (
            <WelcomePanel
              examples={modeExamples}
              modeCopy={modeCopy}
              onSelectExample={selectExample}
              workMode={workMode}
            />
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

      <div ref={resultRef}>
        {error && messages.length === 0 && (
          <div className="error-banner error-banner-action" role="alert">
            <span>{error}</span>
            {!displayedUser && (
              <button type="button" onClick={openAuthDialog}>
                Open account
              </button>
            )}
          </div>
        )}
      </div>

      {loading && (
        <section className="loading-card progress-card" role="status">
          <div className="research-loader" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div>
            <small>FinIntel research desk</small>
            <strong>Building the evidence chain</strong>
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

        <ResearchComposer
          answerDetail={answerDetail}
          authStatus={authStatus}
          externalSignedIn={externalSignedIn}
          inputRef={composerInputRef}
          loading={loading}
          modeCopy={modeCopy}
          onAnswerDetailChange={setAnswerDetail}
          onQueryChange={setActiveQuery}
          onSubmit={submit}
          onWorkModeChange={setWorkMode}
          query={query}
          workMode={workMode}
        />
      </section>

      {authOpen && (
        <AccountDialog
          dialogRef={authDialogRef}
          displayedUser={displayedUser}
          externalAuth={externalAuth}
          onClose={closeAuthDialog}
        />
      )}
    </main>
  );
}
