// The environment is read in one place, packages/env, and every other file imports the parsed
// schema from it. A raw read somewhere else is a key nobody declared.
export default {
  id: "no-raw-env",
  kind: "line",
  files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"],
  exclude: ["packages/env/**", "**/*.test.ts"],
  match: /\bprocess\.env\b/,
  message: '{file}:{line} reads {found}; allowed: import { env } from "@app/env"',
};
