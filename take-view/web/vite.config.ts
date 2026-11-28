import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Dev server. The API stays on the Python process. */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5178,
    proxy: {
      "/api": "http://127.0.0.1:8780",
    },
  },
});
