// The declaration reader every other file uses. It reads the subset of the format stack.yaml is
// written in: maps, lists, scalars, flow lists on one line, comments, one document, no anchors.
// A file outside that subset throws, so nothing reads a half-parsed declaration as clean.
//
//   node scripts/stack-yaml.mjs gates.coverage_lines     the value at a dotted key, as JSON
//   node scripts/stack-yaml.mjs --lines guards           one `key<TAB>value` line per entry
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

class Unsupported extends Error {}

// Inside a quoted value: the characters taken, and whether the quote is still open after them.
function quoted(line, i, quote) {
  const c = line[i];
  if (c === "\\" && quote === '"' && i + 1 < line.length) return [c + line[i + 1], quote];
  return [c, c === quote ? "" : quote];
}

function stripComment(line) {
  let out = "";
  let quote = "";
  for (let i = 0; i < line.length; i += 1) {
    const c = line[i];
    if (quote) {
      const [taken, still] = quoted(line, i, quote);
      out += taken;
      i += taken.length - 1;
      quote = still;
      continue;
    }
    if (c === "#" && (out === "" || /[ \t]$/.test(out))) break;
    if (c === "'" || c === '"') quote = c;
    out += c;
  }
  return out.trimEnd();
}

function unquote(text) {
  const t = text.trim();
  if (t.length >= 2 && t[0] === t[t.length - 1] && (t[0] === '"' || t[0] === "'")) {
    return t.slice(1, -1);
  }
  return t;
}

function scalar(text) {
  const t = text.trim();
  if ((t.startsWith("[") && t.endsWith("]")) || (t.startsWith("{") && t.endsWith("}"))) {
    return flow(t);
  }
  if (t === "true") return true;
  if (t === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
  return unquote(t);
}

const DEPTH = { "[": 1, "{": 1, "]": -1, "}": -1 };

// The top-level items of a flow collection, split on the commas outside brackets and quotes.
function splitFlow(inner) {
  const parts = [];
  let depth = 0;
  let current = "";
  let quote = "";
  for (const c of inner) {
    if (quote) {
      current += c;
      if (c === quote) quote = "";
      continue;
    }
    if (c === "'" || c === '"') quote = c;
    depth += DEPTH[c] ?? 0;
    if (c === "," && depth === 0) {
      parts.push(current);
      current = "";
      continue;
    }
    current += c;
  }
  if (current.trim()) parts.push(current);
  return parts;
}

function flow(text) {
  const parts = splitFlow(text.slice(1, -1).trim());
  if (text.startsWith("[")) return parts.map((p) => scalar(p));
  const out = {};
  for (const p of parts) {
    const i = p.indexOf(":");
    out[unquote(p.slice(0, i))] = scalar(p.slice(i + 1));
  }
  return out;
}

const KEY = /^((?:"[^"]*")|(?:'[^']*')|(?:[^:#]+?))\s*:(?:\s+(.*))?$/;
const BLOCK = /^[|>][+-]?\d*$/;

function tokenize(text) {
  const out = [];
  for (const raw of text.split(/\r?\n/)) {
    const lead = raw.slice(0, raw.length - raw.trimStart().length);
    if (lead.includes("\t")) throw new Unsupported("a tab in the indentation");
    const stripped = stripComment(raw);
    if (!stripped.trim()) continue;
    if (stripped.trim() === "---" || stripped.trim() === "...") {
      throw new Unsupported("more than one document");
    }
    const body = stripped.trim();
    if (/^[&*]/.test(body) || /:\s+[&*]\w/.test(body) || body.startsWith("<<:")) {
      throw new Unsupported("an anchor, an alias, or a merge key");
    }
    out.push({ indent: stripped.length - stripped.trimStart().length, body, raw: raw.trim() });
  }
  return out;
}

function blockScalar(lines, pos, indent) {
  const body = [];
  while (pos < lines.length && lines[pos].indent > indent) {
    body.push(lines[pos].raw);
    pos += 1;
  }
  return [body.join("\n"), pos];
}

function parseBlock(lines, pos, indent) {
  if (pos >= lines.length) return [null, pos];
  if (lines[pos].body.startsWith("-")) return parseSeq(lines, pos, indent);
  return parseMap(lines, pos, indent);
}

function parseSeq(lines, pos, indent) {
  const out = [];
  while (pos < lines.length && lines[pos].indent === indent && lines[pos].body.startsWith("-")) {
    const { indent: ind, body } = lines[pos];
    const m = /^-(\s*)(.*)$/.exec(body);
    const rest = m[2];
    const inner = ind + 1 + m[1].length;
    pos += 1;
    if (!rest) {
      if (pos < lines.length && lines[pos].indent > ind) {
        const [value, next] = parseBlock(lines, pos, lines[pos].indent);
        out.push(value);
        pos = next;
      } else {
        out.push(null);
      }
      continue;
    }
    if (KEY.test(rest)) {
      let take = 0;
      while (pos + take < lines.length && lines[pos + take].indent >= inner) take += 1;
      const sub = [{ indent: inner, body: rest, raw: rest }, ...lines.slice(pos, pos + take)];
      const [value] = parseMap(sub, 0, inner);
      pos += take;
      out.push(value);
      continue;
    }
    out.push(scalar(rest));
  }
  return [out, pos];
}

function parseMap(lines, pos, indent) {
  const out = {};
  while (pos < lines.length && lines[pos].indent === indent) {
    const { indent: ind, body } = lines[pos];
    const m = KEY.exec(body);
    if (!m) throw new Unsupported(`a line that is not a key: ${body.slice(0, 40)}`);
    const key = unquote(m[1]);
    const rest = (m[2] || "").trim();
    pos += 1;
    if (BLOCK.test(rest)) {
      const [value, next] = blockScalar(lines, pos, ind);
      out[key] = value;
      pos = next;
      continue;
    }
    if (rest) {
      out[key] = scalar(rest);
      continue;
    }
    if (pos < lines.length && lines[pos].indent > ind) {
      const [value, next] = parseBlock(lines, pos, lines[pos].indent);
      out[key] = value;
      pos = next;
    } else {
      out[key] = null;
    }
  }
  return [out, pos];
}

export function parseYaml(text) {
  const lines = tokenize(text);
  if (!lines.length) return {};
  const [value, pos] = parseBlock(lines, 0, lines[0].indent);
  if (pos !== lines.length) {
    throw new Unsupported("a block that does not line up with the one above it");
  }
  return value;
}

export function readStack(root = process.cwd()) {
  return parseYaml(readFileSync(join(root, "stack.yaml"), "utf8"));
}

export function get(value, dotted) {
  let cur = value;
  for (const part of dotted.split(".")) {
    if (cur === null || typeof cur !== "object") return undefined;
    cur = cur[part];
  }
  return cur;
}

function main(argv) {
  const lines = argv.includes("--lines");
  const key = argv.filter((a) => !a.startsWith("--"))[0];
  const stack = readStack();
  const value = key ? get(stack, key) : stack;
  if (value === undefined) {
    process.stderr.write(`no ${key} in stack.yaml\n`);
    process.exit(1);
  }
  if (lines && value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) {
      process.stdout.write(`${k}\t${typeof v === "string" ? v : JSON.stringify(v)}\n`);
    }
    return;
  }
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2));
}
