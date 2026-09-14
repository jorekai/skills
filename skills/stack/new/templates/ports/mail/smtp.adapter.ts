// Sends through a mail relay the project runs or rents. Reads MAIL_URL as the `smtp://` address
// with the credential inside it and the sender in its `from` query parameter; MAIL_KEY is unused
// by this adapter because the relay address carries the credential.
import { createTransport } from "nodemailer";
import { env } from "@app/env";
import type { Mail } from "./contract";

function target(): { url: string; from: string } {
  if (!env.MAIL_URL) {
    throw new Error("MAIL_URL is empty: the smtp adapter needs the relay address");
  }
  const url = new URL(env.MAIL_URL);
  const from = url.searchParams.get("from") ?? "noreply@example.com";
  url.searchParams.delete("from");
  return { url: url.toString(), from };
}

export function adapter(): Mail {
  const t = target();
  const transport = createTransport(t.url);
  return {
    send: async (message) => {
      const info = await transport.sendMail({ from: t.from, ...message });
      return { id: info.messageId };
    },
  };
}
