// The unit runner. The two coverage bars come from stack.yaml, and a test that asserts nothing
// fails: `requireAssertions` is the runtime twin of the `no-test-without-assertion` rule.
import { defineConfig } from "vitest/config";
import { readStack } from "./scripts/stack-yaml.mjs";

const { gates } = readStack(import.meta.dirname);

export default defineConfig({
  test: {
    include: ["packages/*/src/**/*.test.ts", "apps/*/**/*.test.ts", "apps/*/**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/.next/**", "**/dist/**", "**/e2e/**"],
    expect: { requireAssertions: true },
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["packages/*/src/**", "apps/*/app/**"],
      // A wired adapter talks to a vendor and has no offline test; the memory one is covered.
      exclude: ["**/*.test.ts", "**/wired.ts", "packages/ports/src/*/!(memory).adapter.ts"],
      thresholds: {
        lines: Number(gates.coverage_lines),
        branches: Number(gates.coverage_branches),
      },
    },
  },
});
