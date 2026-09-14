// A network call without a time limit waits forever on a server that never answers. Every
// fetch carries a signal, and the signal comes from the timeout in @app/config.
export default {
  id: "no-untimed-fetch",
  kind: "block",
  files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"],
  exclude: ["**/*.test.ts", "**/e2e/**"],
  open: /\bfetch\s*\(/,
  require: /\bsignal\b/,
  message:
    "{file}:{line} calls {found} without a signal; allowed: fetch(url, { signal: withTimeout() }) from @app/config",
};
