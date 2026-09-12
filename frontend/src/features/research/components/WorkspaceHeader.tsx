import type { RefObject } from "react";
import type { DisplayedUser, ModeCopy } from "../types";

type WorkspaceHeaderProps = {
  activeConversationTitle?: string;
  authStatus: string;
  currentConversationId: string;
  displayedUser: DisplayedUser;
  mobileAuthLabel: string;
  mobileNavOpen: boolean;
  mobileNavToggleRef: RefObject<HTMLButtonElement | null>;
  modeCopy: ModeCopy;
  onOpenAccount: () => void;
  onOpenMobileNav: () => void;
};

export function WorkspaceHeader({
  activeConversationTitle,
  authStatus,
  currentConversationId,
  displayedUser,
  mobileAuthLabel,
  mobileNavOpen,
  mobileNavToggleRef,
  modeCopy,
  onOpenAccount,
  onOpenMobileNav,
}: WorkspaceHeaderProps) {
  return (
    <header className="chat-topbar">
      <button
        className="mobile-nav-toggle"
        type="button"
        aria-label="Open research navigation"
        aria-controls="research-navigation"
        aria-expanded={mobileNavOpen}
        onClick={onOpenMobileNav}
        ref={mobileNavToggleRef}
      >
        <span className="mobile-nav-icon" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span>Menu</span>
      </button>

      <div className="topbar-heading">
        <p className="eyebrow">{modeCopy.eyebrow}</p>
        <h1 className="topbar-title">{modeCopy.title}</h1>
        {activeConversationTitle && (
          <span className="active-conversation-label">
            {activeConversationTitle}
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
          onClick={onOpenAccount}
          aria-label={
            displayedUser
              ? `Open account menu for ${displayedUser.full_name}`
              : "Open account sign in"
          }
        >
          <span className="nav-auth-icon" aria-hidden="true" />
          <span className="nav-auth-label nav-auth-label-full">
            {displayedUser ? displayedUser.full_name : "Sign Up / Login"}
          </span>
          <span className="nav-auth-label nav-auth-label-mobile">
            {mobileAuthLabel}
          </span>
          <span className="nav-auth-caret" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
