import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward all /api/* calls to the local FastAPI server during development.
      "/api": "http://localhost:8000",
    },
  },
});
