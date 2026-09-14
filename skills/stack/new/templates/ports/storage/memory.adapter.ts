// The offline storage adapter: bytes in a map, urls that name the key. It reads no key.
import type { Storage } from "./contract";

const objects = new Map<string, { bytes: Uint8Array; contentType: string }>();

export function adapter(): Storage {
  return {
    put: async (key, bytes, contentType) => {
      objects.set(key, { bytes: new Uint8Array(bytes), contentType });
    },
    get: async (key) => objects.get(key)?.bytes ?? null,
    remove: async (key) => {
      objects.delete(key);
    },
    url: (key) => `memory://${key}`,
  };
}
