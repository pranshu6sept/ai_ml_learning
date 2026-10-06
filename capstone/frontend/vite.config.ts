/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the page runs on :5173 and the API on :8000; the proxy makes them one origin, so the
// browser never needs CORS. In production the API serves the built files itself (same origin again).
const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ask": API,
      "/feedback": API,
      "/health": API,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: false,
  },
});
