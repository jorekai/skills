// Dead code against the three bars in stack.yaml. Runs the dead-code tool, counts what it
// reports, writes the count to .stack/dead.json for the measuring pass, and fails over a bar.
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { readStack } from "./stack-yaml.mjs";

function report(root) {
  const r = spawnSync("pnpm", ["exec", "knip", "--reporter", "json"], {
    cwd: root,
    encoding: "utf8",
  });
  const text = (r.stdout || "").trim();
  if (!text) {
    process.stdout.write(
      `failed  dead  the dead-code tool wrote nothing: ${(r.stderr || "").trim()}\n`,
    );
    process.exit(1);
  }
  try {
    return JSON.parse(text);
  } catch {
    process.stdout.write("failed  dead  the dead-code tool wrote something that is not JSON\n");
    process.exit(1);
  }
}

function count(json) {
  const issues = Array.isArray(json.issues) ? json.issues : [];
  const size = (x) => (Array.isArray(x) ? x.length : 0);
  return {
    exports: issues.reduce((n, i) => n + size(i.exports) + size(i.types), 0),
    files: size(json.files),
    dependencies: issues.reduce((n, i) => n + size(i.dependencies) + size(i.devDependencies), 0),
  };
}

function main() {
  const root = process.cwd();
  const { gates } = readStack(root);
  const counts = count(report(root));
  mkdirSync(join(root, ".stack"), { recursive: true });
  writeFileSync(join(root, ".stack", "dead.json"), JSON.stringify(counts, null, 2) + "\n");
  const bars = {
    exports: Number(gates.dead_exports_max),
    files: Number(gates.dead_files_max),
    dependencies: Number(gates.dead_deps_max),
  };
  let failed = false;
  for (const [kind, n] of Object.entries(counts)) {
    if (n > bars[kind]) {
      failed = true;
      process.stdout.write(
        `failed  dead  ${n} unused ${kind} over the bar of ${bars[kind]} in stack.yaml; ` +
          "allowed: delete them, or raise the bar through review\n",
      );
    }
  }
  if (failed) process.exit(1);
  process.stdout.write(
    `ok  dead  ${counts.exports} exports, ${counts.files} files, ${counts.dependencies} dependencies unused, all under the bars\n`,
  );
}

main();
