// A vendor module is named in one file: the adapter of its port. Every other file talks to the
// port's contract, so a vendor can be swapped by rewiring one file.
const VENDORS = [
  "@neondatabase/serverless",
  "pg",
  "@vercel/blob",
  "@aws-sdk/client-s3",
  "@clerk/backend",
  "better-auth",
  "nodemailer",
  "@sentry/node",
];
const escaped = VENDORS.map((v) => v.replace(/[/@.-]/g, "\\$&")).join("|");

export default {
  id: "no-vendor-outside-adapter",
  kind: "line",
  files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"],
  exclude: ["packages/ports/src/*/*.adapter.ts"],
  match: new RegExp(`(?:from|import|require)\\s*\\(?\\s*['"](?:${escaped})(?:/[^'"]*)?['"]`),
  message:
    "{file}:{line} imports a vendor module, {found}; allowed: the port through @app/ports/<port>, the adapter is the one file that names the vendor",
};
