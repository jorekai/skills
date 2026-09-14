// Every suppression against the list of names in stack.yaml. What is not named is red now; what
// is past its date is red too. The patterns are built from pieces so this file never holds one.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { pathToFileURL } from "node:url";
import { readStack } from "./stack-yaml.mjs";

const SKIP = new Set([
  ".git",
  "node_modules",
  "dist",
  "build",
  ".next",
  "coverage",
  ".stack",
  ".turbo",
  "out",
  ".tsout",
]);
const SOURCE = /\.(ts|tsx|js|jsx|mjs|cjs)$/;
const SELF = "scripts/waivers.mjs";
const KINDS = {
  type: new RegExp(["@ts-" + "ignore", "@ts-" + "expect-error", "\\bas " + "any\\b"].join("|")),
  lint: new RegExp("eslint-" + "disable"),
  test: new RegExp("\\b(?:it|test|describe)\\." + "(?:skip|only)\\s*\\("),
};

function* walk(dir, root) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) yield* walk(full, root);
    else if (SOURCE.test(name)) yield relative(root, full).split("\\").join("/");
  }
}

function hits(root, files) {
  const out = [];
  for (const file of files) {
    if (file === SELF) continue;
    const lines = readFileSync(join(root, file), "utf8").split("\n");
    lines.forEach((text, i) => {
      for (const [kind, re] of Object.entries(KINDS)) {
        const m = re.exec(text);
        if (m) out.push({ kind, file, line: i + 1, found: m[0] });
      }
    });
  }
  return out;
}

function valid(w) {
  return Boolean(w && w.reason && w.owner && /^\d{4}-\d{2}-\d{2}$/.test(String(w.until)));
}

export function judge(found, waivers, today) {
  const red = [];
  for (const h of found) {
    const w = (waivers || []).find(
      (e) => e && e.kind === h.kind && e.file === h.file && Number(e.line) === h.line,
    );
    if (!valid(w)) {
      red.push({ ...h, why: "no waiver names this file and line" });
    } else if (String(w.until) < today) {
      red.push({ ...h, why: `the waiver expired on ${w.until}` });
    }
  }
  return red;
}

function main(argv) {
  const root = process.cwd();
  const stack = readStack(root);
  const files = argv.length ? argv : [...walk(root, root)];
  const today = new Date().toISOString().slice(0, 10);
  const found = hits(root, files);
  const red = judge(found, stack.waivers, today);
  for (const h of red) {
    process.stdout.write(
      `${h.file}:${h.line}  escape.${h.kind}  ${h.found}  ${h.why}; ` +
        "allowed: a waiver in stack.yaml with reason, until and owner\n",
    );
  }
  if (red.length) process.exit(1);
  process.stdout.write(
    `ok  waivers  ${found.length} suppression(s), every one named and in date\n`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2));
}
