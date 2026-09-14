// Sends events to the analytics ingest over HTTP, on the vendor's host or on one the project
// runs; the adapter is the same, the address differs. Reads ANALYTICS_URL as the ingest base and
// ANALYTICS_KEY as the project key.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Analytics, Properties } from "./contract";

function target(): { base: string; key: string } {
  if (!env.ANALYTICS_URL || !env.ANALYTICS_KEY) {
    throw new Error("ANALYTICS_URL or ANALYTICS_KEY is empty: the posthog adapter needs both");
  }
  return { base: env.ANALYTICS_URL.replace(/\/$/, ""), key: env.ANALYTICS_KEY };
}

async function post(
  t: { base: string; key: string },
  body: Record<string, unknown>,
): Promise<void> {
  const response = await fetch(`${t.base}/i/v0/e/`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ api_key: t.key, ...body }),
    signal: withTimeout(),
  });
  if (!response.ok) {
    throw new Error(`the analytics ingest answered ${response.status}`);
  }
}

export function adapter(): Analytics {
  const t = target();
  const pending: Array<{ event: string; distinct_id: string; properties: Properties }> = [];
  return {
    capture: async (event, distinctId, properties = {}) => {
      pending.push({ event, distinct_id: distinctId, properties });
    },
    flush: async () => {
      const batch = pending.splice(0, pending.length);
      for (const item of batch) {
        await post(t, item);
      }
    },
  };
}
