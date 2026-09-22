import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "./run.mjs";
import rule from "./no-untimed-fetch.rule.mjs";

const path = "packages/ports/src/mail/resend.adapter.ts";
const hit = 'const r = await fetch(url, {\n  method: "POST",\n  body,\n});\n';
const pass =
  'import { withTimeout } from "@app/config";\nconst r = await fetch(url, {\n  method: "POST",\n  signal: withTimeout(),\n});\n';

test("no-untimed-fetch hits a call with no signal in its arguments", () => {
  const found = apply(rule, { text: hit, path });
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 1);
  assert.match(found[0].message, /allowed: fetch\(url, \{ signal: withTimeout\(\) \}\)/);
});

test("no-untimed-fetch passes a call that carries a signal", () => {
  assert.equal(apply(rule, { text: pass, path }).length, 0);
});
