// A promise nobody waits for fails in silence. This is the text twin of the type-aware rule in
// the linter: it sees a statement that starts with a call to fetch or to a function named
// ...Async and is neither awaited, returned, voided nor assigned.
export default {
  id: "no-floating-promise",
  kind: "line",
  files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"],
  match: /^\s*(?:fetch|[A-Za-z_$][\w$]*Async)\s*\(/,
  message:
    "{file}:{line} starts a statement with {found} and drops the promise; allowed: await it, return it, assign it, or void it with a named handler",
};
