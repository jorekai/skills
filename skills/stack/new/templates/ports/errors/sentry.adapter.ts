// Sends caught errors to the error tracker, on the vendor's host or on one the project runs;
// the DSN names the host, so the adapter is the same. Reads ERRORS_URL as the DSN; ERRORS_KEY is
// unused because the DSN carries the key.
import * as Sentry from "@sentry/node";
import { env } from "@app/env";
import type { Errors } from "./contract";

let initialised = false;

function dsn(): string {
  if (!env.ERRORS_URL) {
    throw new Error("ERRORS_URL is empty: the sentry adapter needs the DSN");
  }
  return env.ERRORS_URL;
}

export function adapter(): Errors {
  if (!initialised) {
    Sentry.init({ dsn: dsn() });
    initialised = true;
  }
  return {
    capture: async (error, context = {}) => {
      Sentry.captureException(error, { extra: context });
    },
    flush: async () => {
      await Sentry.flush(2000);
    },
  };
}
