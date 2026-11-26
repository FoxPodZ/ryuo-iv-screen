import {defineConfig} from "vite";
import {resolve} from "node:path";

import {demoApi} from "./demo/mock-api.ts";

export default defineConfig(({mode}) => ({
  plugins: mode === "demo" ? [demoApi()] : [],
  root: resolve(import.meta.dirname, "src"),
  base: "/",
  build: {
    outDir: resolve(import.meta.dirname, "dist"),
    emptyOutDir: true,
    sourcemap: false,
  },
}));
