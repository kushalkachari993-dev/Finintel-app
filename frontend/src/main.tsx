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

function ClerkApp() {
  const auth = useAuth();
  const { user } = useUser();

  return (
    <App
      externalAuth={{
        enabled: true,
        isLoaded: auth.isLoaded,
        isSignedIn: Boolean(auth.isSignedIn),
        email: user?.primaryEmailAddress?.emailAddress || "",
        fullName: user?.fullName || user?.primaryEmailAddress?.emailAddress || "Clerk user",
        getToken: auth.getToken,
        signOut: auth.signOut,
        controls: (
          <>
            <SignedOut>
              <div className="clerk-actions">
                <SignInButton mode="modal">
                  <button type="button">Login</button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <button type="button">Register</button>
                </SignUpButton>
              </div>
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
        <App />
      )}
    </Sentry.ErrorBoundary>
  </React.StrictMode>
);
