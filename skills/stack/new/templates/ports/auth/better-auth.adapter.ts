// Runs the open authentication library in the app process, so the identity store is the
// project's own database. Reads AUTH_KEY as the signing secret and AUTH_URL as the base address.
// The library is wired with its database adapter in `packages/ports/src/db` once that port
// carries a schema; until then `verify` asks the library for the session behind a token and
// `issue` says that sign-in, not this port, mints a token.
import { betterAuth } from "better-auth";
import { env } from "@app/env";
import type { Auth } from "./contract";

function keys(): { secret: string; baseURL: string } {
  if (!env.AUTH_KEY || !env.AUTH_URL) {
    throw new Error("AUTH_KEY or AUTH_URL is empty: the better-auth adapter needs both");
  }
  return { secret: env.AUTH_KEY, baseURL: env.AUTH_URL };
}

function subjectOf(session: unknown): string | null {
  if (session && typeof session === "object" && "user" in session) {
    const user = (session as { user?: { id?: unknown } }).user;
    return typeof user?.id === "string" ? user.id : null;
  }
  return null;
}

export function adapter(): Auth {
  const auth = betterAuth(keys());
  return {
    issue: async () => {
      throw new Error(
        "the library issues a session on sign-in through its routes; the app reads it from the request, it never mints one",
      );
    },
    verify: async (token) => {
      try {
        const session = await auth.api.getSession({
          headers: new Headers({ authorization: `Bearer ${token}` }),
        });
        const subject = subjectOf(session);
        return subject ? { subject } : null;
      } catch {
        return null;
      }
    },
  };
}
