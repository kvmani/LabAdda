import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative asset URLs plus the server-injected <base href> keep the bundle
// prefix-safe: the same build serves "/" and "/labadd-staging/".
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", assetsDir: "assets", sourcemap: false },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  test: { environment: "node" },
} as never);
