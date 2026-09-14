// The offline mail adapter: messages in an outbox array a test can read, nothing sent. It reads
// no key.
import type { Mail, Message } from "./contract";

export const outbox: Message[] = [];

export function adapter(): Mail {
  return {
    send: async (message) => {
      outbox.push({ ...message });
      return { id: `memory-${outbox.length}` };
    },
  };
}
