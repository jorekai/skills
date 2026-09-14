// A test that asserts nothing passes whatever the code does. The runner refuses one at run time;
// this rule counts it in the text, so a skipped run does not hide it.
export default {
  id: "no-test-without-assertion",
  kind: "block",
  files: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"],
  open: /\b(?:it|test)\s*\(/,
  require: /\bexpect\s*\(|\bassert\b/,
  message:
    "{file}:{line} opens {found} and asserts nothing inside it; allowed: at least one expect() in the block",
};
