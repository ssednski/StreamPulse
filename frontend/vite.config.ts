import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In dev, proxy API calls to the FastAPI server so the app can use relative URLs
// (the same URLs work behind nginx in Docker and behind CloudFront on AWS).
const api = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/graphql": api, "/v1": api } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
