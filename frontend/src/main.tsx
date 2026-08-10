import React from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import {
  ClerkProvider,
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
  useAuth,
  useSignIn,
  useUser,
} from "@clerk/clerk-react";
import App from "./App";
import "./styles.css";

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";
const sentryDsn = import.meta.env.VITE_SENTRY_DSN || "";

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.VITE_APP_ENV || "development",
    release: import.meta.env.VITE_APP_RELEASE || "finintel-ai-frontend@0.1.0",
    tracesSampleRate: Number(
      import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || "0.05"
    ),
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
  });
}

function clerkErrorMessage(error: unknown, fallback: string) {
  if (!error || typeof error !== "object") {
    return fallback;
  }

  const clerkErrors = (error as {
    errors?: Array<{ longMessage?: string; message?: string }>;
  }).errors;
  return clerkErrors?.[0]?.longMessage || clerkErrors?.[0]?.message || fallback;
}

function ClerkAccountControls() {
  const { isLoaded, signIn, setActive } = useSignIn();
  const [resetOpen, setResetOpen] = React.useState(false);
  const [codeSent, setCodeSent] = React.useState(false);
  const [email, setEmail] = React.useState("");
  const [code, setCode] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const closeReset = () => {
    setResetOpen(false);
    setCodeSent(false);
    setEmail("");
    setCode("");
    setPassword("");
    setConfirmPassword("");
    setError("");
  };

  const sendResetCode = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isLoaded || !signIn) {
      return;
    }

    setBusy(true);
    setError("");
    try {
      await signIn.create({
        strategy: "reset_password_email_code",
        identifier: email.trim(),
      });
      setCodeSent(true);
    } catch {
      setError("We couldn't start password recovery. Check the email address and try again.");
    } finally {
      setBusy(false);
    }
  };

  const resetPassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isLoaded || !signIn || !setActive) {
      return;
    }
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const result = await signIn.attemptFirstFactor({
        strategy: "reset_password_email_code",
        code: code.trim(),
        password,
      });

      if (result.status === "complete" && result.createdSessionId) {
        await setActive({ session: result.createdSessionId });
        closeReset();
        return;
      }

      setError("Clerk requires an additional verification step. Return to login to continue.");
    } catch (resetError) {
      setError(clerkErrorMessage(resetError, "Clerk could not reset the password. Try again."));
    } finally {
      setBusy(false);
    }
  };

  if (resetOpen) {
    return (
      <div className="clerk-reset-flow">
        <div className="clerk-reset-heading">
          <strong>Reset password</strong>
          <p>
            {codeSent
              ? "Enter the code Clerk emailed you and choose a new password."
              : "Enter your account email and Clerk will send a verification code."}
          </p>
        </div>

        {!codeSent ? (
          <form onSubmit={sendResetCode}>
            <label htmlFor="clerk-reset-email">Email address</label>
            <input
              id="clerk-reset-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            {error && <p className="clerk-reset-error" role="alert">{error}</p>}
            <div className="clerk-reset-actions">
              <button className="secondary" type="button" onClick={closeReset}>
                Back
              </button>
              <button type="submit" disabled={busy || !isLoaded}>
                {busy ? "Sending..." : "Send code"}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={resetPassword}>
            <label htmlFor="clerk-reset-code">Verification code</label>
            <input
              id="clerk-reset-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
            />
            <label htmlFor="clerk-reset-password">New password</label>
            <input
              id="clerk-reset-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <label htmlFor="clerk-reset-confirm">Confirm new password</label>
            <input
              id="clerk-reset-confirm"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
            {error && <p className="clerk-reset-error" role="alert">{error}</p>}
            <div className="clerk-reset-actions">
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  setCodeSent(false);
                  setCode("");
                  setPassword("");
                  setConfirmPassword("");
                  setError("");
                }}
              >
                Change email
              </button>
              <button type="submit" disabled={busy || !isLoaded}>
                {busy ? "Resetting..." : "Reset password"}
              </button>
            </div>
          </form>
        )}
      </div>
    );
  }

  return (
    <>
      <div className="clerk-actions">
        <SignInButton mode="modal">
          <button type="button">Login</button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button type="button">Register</button>
        </SignUpButton>
      </div>
      <button
        className="clerk-forgot-password"
        type="button"
        onClick={() => setResetOpen(true)}
      >
        Forgot password?
      </button>
    </>
  );
}

function ClerkApp() {
  const auth = useAuth();
  const { user } = useUser();

  return (
    <App
      externalAuth={{
        isLoaded: auth.isLoaded,
        isSignedIn: Boolean(auth.isSignedIn),
        email: user?.primaryEmailAddress?.emailAddress || "",
        fullName: user?.fullName || user?.primaryEmailAddress?.emailAddress || "Clerk user",
        getToken: auth.getToken,
        controls: (
          <>
            <SignedOut>
              <ClerkAccountControls />
            </SignedOut>
            <SignedIn>
              <UserButton />
            </SignedIn>
          </>
        ),
      }}
    />
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={<p>Something went wrong.</p>}>
      {clerkPublishableKey ? (
        <ClerkProvider publishableKey={clerkPublishableKey}>
          <ClerkApp />
        </ClerkProvider>
      ) : (
        <main className="configuration-error" role="alert">
          Authentication is temporarily unavailable.
        </main>
      )}
    </Sentry.ErrorBoundary>
  </React.StrictMode>
);
