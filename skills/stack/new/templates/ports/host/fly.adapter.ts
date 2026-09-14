// The app runs as a machine on the third target. Reads HOST_URL as the public address; HOST_KEY
// is the deploy token the platform's client reads from the environment and is not read here.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Host } from "./contract";

function base(): string {
  if (!env.HOST_URL) {
    throw new Error("HOST_URL is empty: the fly adapter needs the public address");
  }
  return env.HOST_URL.replace(/\/$/, "");
}

export function adapter(): Host {
  const address = base();
  const healthPath = "/api/health";
  return {
    name: "fly",
    healthPath,
    url: (path) => `${address}${path.startsWith("/") ? path : `/${path}`}`,
    up: async () => {
      const response = await fetch(`${address}${healthPath}`, { signal: withTimeout() });
      return response.ok;
    },
  };
}
