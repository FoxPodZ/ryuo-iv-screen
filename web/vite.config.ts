import {defineConfig} from "vite";
import {resolve} from "node:path";

export default defineConfig({
  root: resolve(import.meta.dirname, "src"),
  base: "/",
  build: {
    outDir: resolve(import.meta.dirname, "dist"),
    emptyOutDir: true,
    sourcemap: false,
  },
});
