import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const clerkKey = env.VITE_CLERK_PUBLISHABLE_KEY || "";
  const isProduction = mode === "production" && env.VITE_APP_ENV === "production";

  if (isProduction && clerkKey.startsWith("pk_test_")) {
    throw new Error(
      "Production builds require a Clerk production publishable key (pk_live_...)."
    );
  }

  return {
    plugins: [react()],
  };
});
