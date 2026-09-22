import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "./run.mjs";
import rule from "./no-vendor-outside-adapter.rule.mjs";

const path = "apps/web/app/api/health/route.ts";
const hit = 'import { neon } from "@neondatabase/serverless";\n';
const pass = 'import { db } from "@app/ports/db";\n';

test("no-vendor-outside-adapter hits a vendor import outside its adapter", () => {
  const found = apply(rule, { text: hit, path });
  assert.equal(found.length, 1);
  assert.match(found[0].message, /allowed: the port through @app\/ports/);
});

test("no-vendor-outside-adapter passes the port, and the adapter file itself", () => {
  assert.equal(apply(rule, { text: pass, path }).length, 0);
  assert.equal(
    apply(rule, { text: hit, path: "packages/ports/src/db/neon-http.adapter.ts" }).length,
    0,
  );
});
