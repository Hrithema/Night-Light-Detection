import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Any request the browser makes to /api/... is forwarded by the Vite dev
// server to the Flask backend. This is the link between React and Python.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
      },
    },
  },
});
