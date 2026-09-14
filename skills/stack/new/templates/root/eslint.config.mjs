// The linter, with the four complexity bars read from stack.yaml. No number lives here: a bar
// moves in the declaration, under CODEOWNERS, and this file follows it.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import { readStack } from "./scripts/stack-yaml.mjs";

const { gates } = readStack(import.meta.dirname);
const lines = { skipBlankLines: true, skipComments: true };

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/.next/**",
      "**/dist/**",
      "**/.tsout/**",
      "coverage/**",
      ".stack/**",
      "**/*.d.ts",
      "**/*.d.mts",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    rules: {
      complexity: ["error", Number(gates.max_complexity)],
      "max-lines": ["error", { max: Number(gates.max_file_lines), ...lines }],
      "max-lines-per-function": ["error", { max: Number(gates.max_function_lines), ...lines }],
      "max-params": ["error", Number(gates.max_params)],
      "@typescript-eslint/no-floating-promises": "error",
      // An offline adapter answers a promise without waiting for anything; that is not a floating one.
      "@typescript-eslint/require-await": "off",
    },
  },
  {
    // The tooling of the gate runs on the platform, not in a browser, and is not typed.
    files: ["**/*.mjs", "**/*.js", "**/*.cjs"],
    ...tseslint.configs.disableTypeChecked,
    languageOptions: {
      ...tseslint.configs.disableTypeChecked.languageOptions,
      globals: {
        process: "readonly",
        console: "readonly",
        Buffer: "readonly",
        URL: "readonly",
        fetch: "readonly",
        AbortSignal: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
      },
    },
  },
);
