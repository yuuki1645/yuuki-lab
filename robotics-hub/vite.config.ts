import { defineConfig, searchForWorkspaceRoot } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "node:path";

const atomManualDir = path.resolve(__dirname, "../atom-rt/docs/field-manual");

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  // 現場手帳の Markdown は robotics-hub の外（atom-rt）にある。
  server: {
    fs: {
      allow: [searchForWorkspaceRoot(process.cwd()), atomManualDir],
    },
  },
});
