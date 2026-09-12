import type { FormEvent, KeyboardEvent, RefObject } from "react";
import type { AnswerDetail, ModeCopy, WorkMode } from "../types";

type ResearchComposerProps = {
  answerDetail: AnswerDetail;
  authStatus: string;
  externalSignedIn: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  loading: boolean;
  modeCopy: ModeCopy;
  onAnswerDetailChange: (detail: AnswerDetail) => void;
  onQueryChange: (query: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onWorkModeChange: (mode: WorkMode) => void;
  query: string;
  workMode: WorkMode;
};

export function ResearchComposer({
  answerDetail,
  authStatus,
  externalSignedIn,
  inputRef,
  loading,
  modeCopy,
  onAnswerDetailChange,
  onQueryChange,
  onSubmit,
  onWorkModeChange,
  query,
  workMode,
}: ResearchComposerProps) {
  function submitOnEnter(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form className="chat-composer" onSubmit={onSubmit}>
      <div className="composer-shell">
        <div className="composer-toolbar">
          <span id="composer-status">
            <span
              className={`composer-status-dot ${externalSignedIn ? "composer-status-dot-online" : ""}`}
              aria-hidden="true"
            />
            {authStatus}
          </span>
          <div className="composer-actions">
            <div className="mode-switch mode-switch-inline" aria-label="Work mode">
              <button
                className={workMode === "chat" ? "active" : ""}
                type="button"
                aria-pressed={workMode === "chat"}
                onClick={() => onWorkModeChange("chat")}
              >
                Chat
              </button>
              <button
                className={workMode === "report" ? "active" : ""}
                type="button"
                aria-pressed={workMode === "report"}
                onClick={() => onWorkModeChange("report")}
              >
                Report
              </button>
            </div>
            <div className="detail-toggle" aria-label="Answer detail">
              <button
                className={workMode === "chat" && answerDetail === "brief" ? "active" : ""}
                type="button"
                aria-pressed={workMode === "chat" && answerDetail === "brief"}
                onClick={() => onAnswerDetailChange("brief")}
                disabled={workMode === "report"}
              >
                Brief
              </button>
              <button
                className={workMode === "report" || answerDetail === "detailed" ? "active" : ""}
                type="button"
                aria-pressed={workMode === "report" || answerDetail === "detailed"}
                onClick={() => onAnswerDetailChange("detailed")}
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
            ref={inputRef}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={submitOnEnter}
            placeholder={modeCopy.placeholder}
            aria-describedby="composer-status composer-guidance"
            rows={2}
          />
          <button
            aria-label={loading ? "Analyzing..." : modeCopy.submit}
            disabled={loading || !query.trim()}
            type="submit"
          >
            <span className="submit-label-full">
              {loading ? "Analyzing..." : modeCopy.submit}
            </span>
            <span className="submit-label-mobile" aria-hidden="true">
              {loading ? "Wait" : workMode === "report" ? "Create" : "Run"}
            </span>
            <span className="submit-arrow" aria-hidden="true">↗</span>
          </button>
        </div>
        <div className="composer-guidance" id="composer-guidance">
          <span>Enter to submit · Shift + Enter for a new line</span>
          <span>Verify market data before acting</span>
        </div>
      </div>
    </form>
  );
}
