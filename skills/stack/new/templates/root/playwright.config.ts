// The browser runner: one project, one browser, the app started by the runner itself.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "apps/web/e2e",
  timeout: 30_000,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://localhost:3000" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm --filter web dev",
    port: 3000,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
