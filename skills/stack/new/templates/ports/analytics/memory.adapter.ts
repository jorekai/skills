// The offline analytics adapter: events in an array a test can read, nothing sent. It reads no key.
import type { Analytics, Properties } from "./contract";

export const events: Array<{ event: string; distinctId: string; properties: Properties }> = [];

export function adapter(): Analytics {
  return {
    capture: async (event, distinctId, properties = {}) => {
      events.push({ event, distinctId, properties: { ...properties } });
    },
    flush: async () => undefined,
  };
}
