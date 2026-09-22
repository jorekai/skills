// The rule engine: every rules/<id>.rule.mjs, run over the tree after its own test proved it
// fires. A rule without a test beside it is refused, because a rule that looks like a lock and
// catches nothing is worse than none.
//
//   node rules/run.mjs [file ...]     the tests, then every rule over the tree or the files
//   node rules/run.mjs --self-test    the tests only
//
// A rule exports one object: id, kind (line, block, edge), files (globs), message, and the keys
// of its kind. A hit prints `<file>:<line>  <id>  <message>`. The message names what was found
// and what is allowed instead, so the reader can fix the line instead of guessing.
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { readStack } from "../scripts/stack-yaml.mjs";
import { span } from "./span.mjs";

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
const IMPORTS = [
  /^\s*(?:import|export)\b[^'"]*?from\s*['"]([^'"]+)['"]/,
  /^\s*import\s*['"]([^'"]+)['"]/,
  /import\(\s*['"]([^'"]+)['"]\s*\)/,
  /require\(\s*['"]([^'"]+)['"]\s*\)/,
];

export function globToRegex(glob) {
  let out = "^";
  for (let i = 0; i < glob.length; i += 1) {
    const c = glob[i];
    if (c === "*") {
      if (glob[i + 1] === "*") {
        out += glob[i + 2] === "/" ? "(?:.*/)?" : ".*";
        i += glob[i + 2] === "/" ? 2 : 1;
      } else {
        out += "[^/]*";
      }
    } else if (c === "{") {
      const end = glob.indexOf("}", i);
      out +=
        "(?:" +
        glob
          .slice(i + 1, end)
          .split(",")
          .join("|") +
        ")";
      i = end;
    } else if (".+?^$()|[]\\".includes(c)) {
      out += "\\" + c;
    } else {
      out += c;
    }
  }
  return new RegExp(out + "$");
}

export function matchesFiles(rule, path) {
  const files = rule.files || ["**/*.{ts,tsx,js,jsx,mjs,cjs}"];
  const exclude = rule.exclude || [];
  return (
    files.some((g) => globToRegex(g).test(path)) && !exclude.some((g) => globToRegex(g).test(path))
  );
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

function fill(message, hit) {
  return message
    .replace("{file}", hit.file)
    .replace("{line}", String(hit.line))
    .replace("{found}", hit.found)
    .replace("{allowed}", hit.allowed || "");
}

function ownWorkspace(path, workspaces) {
  return Object.keys(workspaces).find((w) => path === w || path.startsWith(w + "/")) || "";
}

// The workspace an import targets: by package name, or by the resolved relative path.
function targetWorkspace(spec, path, ctx) {
  if (spec.startsWith(".")) {
    const full = relative(".", resolve(dirname(path), spec))
      .split("\\")
      .join("/");
    return ownWorkspace(full, ctx.workspaces);
  }
  for (const [name, dir] of Object.entries(ctx.names || {})) {
    if (spec === name || spec.startsWith(name + "/")) return dir;
  }
  return "";
}

function applyLine(rule, source) {
  const out = [];
  source.text.split("\n").forEach((line, i) => {
    const m = rule.match.exec(line);
    if (!m) return;
    if (rule.allow && rule.allow.test(line)) return;
    out.push({ file: source.path, line: i + 1, id: rule.id, found: m[0].trim() });
  });
  return out;
}

function applyBlock(rule, source) {
  const { text, path } = source;
  const out = [];
  const open = new RegExp(
    rule.open.source,
    rule.open.flags.includes("g") ? rule.open.flags : rule.open.flags + "g",
  );
  let m;
  while ((m = open.exec(text))) {
    const [start, end] = span(text, m.index + m[0].length - 1);
    const body = text.slice(start, end);
    if (!rule.require.test(body)) {
      out.push({ file: path, line: lineOf(text, m.index), id: rule.id, found: m[0].trim() });
    }
    open.lastIndex = Math.max(open.lastIndex, end);
  }
  return out;
}

function applyEdge(rule, source, ctx) {
  const { text, path } = source;
  const out = [];
  const own = ownWorkspace(path, ctx.workspaces);
  if (!own) return out;
  const allowed = ctx.workspaces[own] || [];
  text.split("\n").forEach((line, i) => {
    for (const re of IMPORTS) {
      const m = re.exec(line);
      if (!m) continue;
      const target = targetWorkspace(m[1], path, ctx);
      if (target && target !== own && !allowed.includes(target)) {
        out.push({
          file: path,
          line: i + 1,
          id: rule.id,
          found: m[1],
          allowed: allowed.length ? allowed.join(", ") : "nothing",
        });
      }
      break;
    }
  });
  return out;
}

function waived(hit, rule, ctx) {
  if (!rule.waivable) return false;
  const today = ctx.today || new Date().toISOString().slice(0, 10);
  return (ctx.waivers || []).some(
    (w) =>
      w &&
      w.kind === rule.waivable &&
      w.file === hit.file &&
      Number(w.line) === hit.line &&
      w.reason &&
      w.owner &&
      /^\d{4}-\d{2}-\d{2}$/.test(String(w.until)) &&
      String(w.until) >= today,
  );
}

// One rule over one file. `source` is `{ text, path }`; `ctx` carries workspaces, package names,
// waivers and today.
export function apply(rule, source, ctx = {}) {
  if (!matchesFiles(rule, source.path)) return [];
  const hits =
    rule.kind === "line"
      ? applyLine(rule, source)
      : rule.kind === "block"
        ? applyBlock(rule, source)
        : rule.kind === "edge"
          ? applyEdge(rule, source, ctx)
          : [];
  return hits
    .filter((h) => !waived(h, rule, ctx))
    .map((h) => ({ ...h, message: fill(rule.message, h) }));
}

function* walk(dir, root) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full, root);
    else if (SOURCE.test(name)) yield relative(root, full).split("\\").join("/");
  }
}

function packageNames(root, workspaces) {
  const names = {};
  for (const dir of Object.keys(workspaces)) {
    const manifest = join(root, dir, "package.json");
    let name = "@app/" + basename(dir);
    if (existsSync(manifest)) {
      try {
        name = JSON.parse(readFileSync(manifest, "utf8")).name || name;
      } catch {
        // an unreadable manifest keeps the fallback name
      }
    }
    names[name] = dir;
  }
  return names;
}

async function loadRules(dir) {
  const rules = [];
  const refused = [];
  for (const name of readdirSync(dir).sort()) {
    if (!name.endsWith(".rule.mjs")) continue;
    const id = name.slice(0, -".rule.mjs".length);
    if (!existsSync(join(dir, `${id}.test.mjs`))) {
      refused.push(id);
      continue;
    }
    const mod = await import(pathToFileURL(join(dir, name)).href);
    rules.push(mod.default);
  }
  return { rules, refused };
}

function say(line) {
  process.stdout.write(line + "\n");
}

// The tests of every rule run first; a rule whose test fails is not trusted and nothing runs.
function proveRules(root) {
  const tests = spawnSync(process.execPath, ["--test", "rules/*.test.mjs"], {
    cwd: root,
    encoding: "utf8",
  });
  if (tests.status === 0) return true;
  say("failed  rules  a rule's own test fails, so the rule is not trusted:");
  process.stdout.write((tests.stdout || "") + (tests.stderr || ""));
  return false;
}

function scan(root, paths, ctx) {
  let hits = 0;
  for (const path of paths) {
    if (!existsSync(join(root, path))) continue;
    const text = readFileSync(join(root, path), "utf8");
    for (const rule of ctx.rules) {
      for (const h of apply(rule, { text, path }, ctx)) {
        hits += 1;
        say(`${h.file}:${h.line}  ${h.id}  ${h.message}`);
      }
    }
  }
  return hits;
}

function gaps(refused, declared, rules) {
  for (const id of refused) {
    say(
      `rules/${id}.rule.mjs  guard.rulegap  no rules/${id}.test.mjs beside it, so the rule is not run; allowed: a test with a hit and a pass fixture`,
    );
  }
  const missing = declared.filter((id) => !rules.some((r) => r.id === id));
  for (const id of missing) {
    say(
      `rules/${id}.rule.mjs  guard.rulegap  stack.yaml names the rule and no file carries it; allowed: the rule with its test, or the line removed through review`,
    );
  }
  return refused.length + missing.length;
}

// What every rule reads while it runs: the boundaries, the package names, the waivers, and the
// rules the declaration names, which is a subset of the rules that proved themselves.
function context(root, stack, rules) {
  const declared = stack.rules ?? [];
  const workspaces = stack.workspaces ?? {};
  return {
    workspaces,
    names: packageNames(root, workspaces),
    waivers: stack.waivers ?? [],
    rules: rules.filter((r) => declared.includes(r.id)),
  };
}

async function main(argv) {
  const root = process.cwd();
  const { rules, refused } = await loadRules(join(root, "rules"));
  if (!proveRules(root)) process.exit(1);
  if (argv.includes("--self-test")) {
    if (gaps(refused, [], rules)) process.exit(1);
    say(`ok  rules  ${rules.length} rule(s) proved by their tests`);
    return;
  }
  const stack = readStack(root);
  const ctx = context(root, stack, rules);
  const files = argv.filter((a) => !a.startsWith("--"));
  const paths = files.length ? files : [...walk(root, root)];
  const hits = scan(root, paths, ctx);
  if (hits + gaps(refused, stack.rules ?? [], rules)) process.exit(1);
  say(`ok  rules  ${rules.length} rule(s) over ${paths.length} file(s)`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main(process.argv.slice(2));
}
