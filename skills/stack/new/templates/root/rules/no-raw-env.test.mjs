import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "./run.mjs";
import rule from "./no-raw-env.rule.mjs";

const path = "packages/ui/src/index.ts";
const hit = "const url = process.env.DB_URL;\n";
const pass = 'import { env } from "@app/env";\nconst url = env.DB_URL;\n';

test("no-raw-env hits a raw read of the environment", () => {
  const found = apply(rule, hit, path);
  assert.equal(found.length, 1);
  assert.match(found[0].message, /allowed: import \{ env \} from "@app\/env"/);
});

test("no-raw-env passes the import from the schema, and packages/env itself", () => {
  assert.equal(apply(rule, pass, path).length, 0);
  assert.equal(apply(rule, hit, "packages/env/src/index.ts").length, 0);
});
