import { defineConfig } from "vite";
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = dirname(fileURLToPath(import.meta.url));
function files(folder) {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? files(join(folder, entry.name)) : [join(folder, entry.name)],
  );
}
function sourceDigest() {
  const paths = [...files(join(frontend, "src")), ...[
    "index.html", "package.json", "package-lock.json", "vite.config.js",
  ].map((name) => join(frontend, name))];
  const hash = createHash("sha256");
  const normalized = (path) => relative(frontend, path).split("\\").join("/");
  for (const path of paths.sort((a, b) => normalized(a) < normalized(b) ? -1 : normalized(a) > normalized(b) ? 1 : 0)) {
    hash.update(relative(frontend, path).split("\\").join("/"));
    hash.update("\0"); hash.update(readFileSync(path)); hash.update("\0");
  }
  return hash.digest("hex");
}
export default defineConfig({
  plugins: [{
    name: "company-brain-build-version",
    generateBundle(_options, bundle) {
      this.emitFile({ type: "asset", fileName: "build-info.json", source: JSON.stringify({
        source_digest: sourceDigest(), assets: Object.keys(bundle),
      }) });
    },
  }],
  build: { outDir: "../src/brain/web/app", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
});
