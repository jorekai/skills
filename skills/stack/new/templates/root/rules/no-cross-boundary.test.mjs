import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "./run.mjs";
import rule from "./no-cross-boundary.rule.mjs";

const ctx = {
  workspaces: { "packages/ui": ["packages/config"], "packages/ports": [], "packages/config": [] },
  names: {
    "@app/config": "packages/config",
    "@app/ports": "packages/ports",
    "@app/ui": "packages/ui",
  },
  waivers: [],
  today: "2026-09-14",
};
const path = "packages/ui/src/index.ts";
const hit = 'import { db } from "@app/ports/db";\n';
const pass = 'import { TIMEOUT_MS } from "@app/config";\nimport { cn } from "./cn";\n';

test("no-cross-boundary hits an import over an edge the declaration does not name", () => {
  const found = apply(rule, hit, path, ctx);
  assert.equal(found.length, 1);
  assert.match(found[0].message, /allowed from this workspace: packages\/config/);
});

test("no-cross-boundary passes an allowed edge and an import inside the workspace", () => {
  assert.equal(apply(rule, pass, path, ctx).length, 0);
});

test("no-cross-boundary honours a boundary waiver that names the line and is in date", () => {
  const waived = {
    ...ctx,
    waivers: [
      { kind: "boundary", file: path, line: 1, reason: "r", until: "2026-12-31", owner: "o" },
    ],
  };
  assert.equal(apply(rule, hit, path, waived).length, 0);
  const expired = { ...waived, waivers: [{ ...waived.waivers[0], until: "2026-01-01" }] };
  assert.equal(apply(rule, hit, path, expired).length, 1);
});
