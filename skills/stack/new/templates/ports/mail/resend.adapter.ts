// Sends through the mail API over HTTP. Reads MAIL_URL as the API base, with the sender in its
// `from` query parameter, and MAIL_KEY as the bearer token.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Mail } from "./contract";

function target(): { base: string; from: string; key: string } {
  if (!env.MAIL_URL || !env.MAIL_KEY) {
    throw new Error("MAIL_URL or MAIL_KEY is empty: the resend adapter needs both");
  }
  const url = new URL(env.MAIL_URL);
  const from = url.searchParams.get("from") ?? "noreply@example.com";
  url.search = "";
  return { base: url.toString().replace(/\/$/, ""), from, key: env.MAIL_KEY };
}

export function adapter(): Mail {
  const t = target();
  return {
    send: async (message) => {
      const response = await fetch(`${t.base}/emails`, {
        method: "POST",
        headers: { authorization: `Bearer ${t.key}`, "content-type": "application/json" },
        body: JSON.stringify({ from: t.from, ...message }),
        signal: withTimeout(),
      });
      if (!response.ok) {
        throw new Error(`the mail API answered ${response.status} for ${message.to}`);
      }
      const body = (await response.json()) as { id?: unknown };
      return { id: typeof body.id === "string" ? body.id : "" };
    },
  };
}
