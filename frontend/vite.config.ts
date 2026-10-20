import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: { manualChunks: { charts: ["recharts"], vendor: ["react", "react-dom", "react-router-dom", "@tanstack/react-query", "axios"] } },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
