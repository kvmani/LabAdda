import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const version = (JSON.parse(readFileSync("./package.json", "utf8")) as { version: string }).version;

/** Build identity: set by scripts/release.py for a bundle, else asked of git; unknown stays empty. */
function fromGit(...args: string[]): string {
  try {
    return execFileSync("git", args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
}
const commit = process.env.LABADDA_BUILD_COMMIT || fromGit("rev-parse", "HEAD");
const commitDate = process.env.LABADDA_BUILD_DATE || fromGit("log", "-1", "--format=%cs");

// Relative asset URLs plus the server-injected <base href> keep the bundle
// prefix-safe: the same build serves "/" and "/labadda-staging/".
export default defineConfig({
  base: "./",
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __APP_COMMIT__: JSON.stringify(commit),
    __APP_COMMIT_DATE__: JSON.stringify(commitDate),
  },
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
