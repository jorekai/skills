// Verifies session tokens against the managed identity provider through its backend client.
// Reads AUTH_KEY as the secret key; AUTH_URL is the issuer and may stay empty.
import { verifyToken } from "@clerk/backend";
import { env } from "@app/env";
import type { Auth } from "./contract";

function secretKey(): string {
  if (!env.AUTH_KEY) {
    throw new Error("AUTH_KEY is empty: the clerk adapter needs the secret key");
  }
  return env.AUTH_KEY;
}

export function adapter(): Auth {
  const key = secretKey();
  return {
    issue: async () => {
      throw new Error(
        "the managed provider issues tokens on sign-in; the app reads them from the request, it never mints one",
      );
    },
    verify: async (token) => {
      try {
        const payload = await verifyToken(token, { secretKey: key });
        return payload.sub ? { subject: payload.sub } : null;
      } catch {
        return null;
      }
    },
  };
}
