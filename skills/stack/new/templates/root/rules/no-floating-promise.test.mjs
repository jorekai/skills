import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "./run.mjs";
import rule from "./no-floating-promise.rule.mjs";

const path = "apps/web/app/api/jobs/[name]/route.ts";
const hit = "sendAsync(mail);\n";
const pass =
  "await sendAsync(mail);\nconst r = await fetch(url, { signal });\nreturn sendAsync(mail);\nvoid sendAsync(mail).catch(report);\n";

test("no-floating-promise hits a statement that drops the promise", () => {
  const found = apply(rule, hit, path);
  assert.equal(found.length, 1);
  assert.match(found[0].message, /allowed: await it, return it, assign it, or void it/);
});

test("no-floating-promise passes an awaited, returned, assigned or voided call", () => {
  assert.equal(apply(rule, pass, path).length, 0);
});
