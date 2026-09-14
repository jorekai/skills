// The offline auth adapter: tokens in a map, deterministic, nothing signed. It reads no key.
import type { Auth } from "./contract";

const sessions = new Map<string, string>();
let counter = 0;

export function adapter(): Auth {
  return {
    issue: async (subject) => {
      counter += 1;
      const token = `memory-${counter}`;
      sessions.set(token, subject);
      return token;
    },
    verify: async (token) => {
      const subject = sessions.get(token);
      return subject === undefined ? null : { subject };
    },
  };
}
