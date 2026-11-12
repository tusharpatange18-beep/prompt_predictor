import { build } from "esbuild";
import { cpSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });
cpSync("manifest.json", "dist/manifest.json");

await build({
  entryPoints: {
    content: "src/content/index.ts",
    background: "src/background/index.ts",
  },
  bundle: true,
  outdir: "dist",
  target: "chrome120",
  sourcemap: true,
});
