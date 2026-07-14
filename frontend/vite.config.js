import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api":           "http://127.0.0.1:5001",
      "/get_faqs":      "http://127.0.0.1:5001",
      "/clear_history": "http://127.0.0.1:5001",
      "/health":        "http://127.0.0.1:5001",
    },
  },
});