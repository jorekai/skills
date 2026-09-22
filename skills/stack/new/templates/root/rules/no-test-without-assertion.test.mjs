import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "./run.mjs";
import rule from "./no-test-without-assertion.rule.mjs";

const path = "packages/ui/src/index.test.ts";
const hit = 'it("joins class names", () => {\n  cn("a", "b");\n});\n';
const pass = 'it("joins class names", () => {\n  expect(cn("a", "b")).toBe("a b");\n});\n';

test("no-test-without-assertion hits a block with no assertion", () => {
  const found = apply(rule, { text: hit, path });
  assert.equal(found.length, 1);
  assert.match(found[0].message, /allowed: at least one expect\(\)/);
});

test("no-test-without-assertion passes a block that asserts, and a file that is not a test", () => {
  assert.equal(apply(rule, { text: pass, path }).length, 0);
  assert.equal(apply(rule, { text: hit, path: "packages/ui/src/index.ts" }).length, 0);
});
