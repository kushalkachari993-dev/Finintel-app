import type { RefObject } from "react";
import type { DisplayedUser, ExternalAuth } from "../types";

type AccountDialogProps = {
  dialogRef: RefObject<HTMLElement | null>;
  displayedUser: DisplayedUser;
  externalAuth: ExternalAuth;
  onClose: () => void;
};

export function AccountDialog({
  dialogRef,
  displayedUser,
  externalAuth,
  onClose,
}: AccountDialogProps) {
  return (
    <div
      className="auth-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        className="auth-modal"
        aria-modal="true"
        role="dialog"
        aria-labelledby="auth-modal-title"
        aria-describedby="auth-modal-copy"
        tabIndex={-1}
        ref={dialogRef}
      >
        <button
          className="auth-modal-close"
          type="button"
          aria-label="Close account dialog"
          onClick={onClose}
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

        <div className="auth-card auth-card-modal">
          {externalAuth.isLoaded && externalAuth.isSignedIn ? (
            <div className="account-summary">
              <strong>{externalAuth.fullName}</strong>
              <small>{externalAuth.email}</small>
            </div>
          ) : (
            <small>Use your Clerk account to save history.</small>
          )}
          {externalAuth.controls}
        </div>
      </section>
    </div>
  );
}
