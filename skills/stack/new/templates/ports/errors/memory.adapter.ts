// The offline errors adapter: captured errors in an array a test can read, nothing sent. It
// reads no key.
import type { Context, Errors } from "./contract";

export const captured: Array<{ message: string; context: Context }> = [];

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function adapter(): Errors {
  return {
    capture: async (error, context = {}) => {
      captured.push({ message: messageOf(error), context: { ...context } });
    },
    flush: async () => undefined,
  };
}
