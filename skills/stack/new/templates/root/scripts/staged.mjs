// The staged source files, one per line, for the hook's run of the gate.
import { execFileSync } from "node:child_process";

const SOURCE = /\.(ts|tsx|js|jsx|mjs|cjs)$/;

let listed = "";
try {
  listed = execFileSync("git", ["diff", "--cached", "--name-only", "--diff-filter=ACMR"], {
    encoding: "utf8",
  });
} catch {
  listed = "";
}
const files = listed
  .split("\n")
  .map((l) => l.trim())
  .filter((l) => l && SOURCE.test(l));
process.stdout.write(files.join("\n") + (files.length ? "\n" : ""));
