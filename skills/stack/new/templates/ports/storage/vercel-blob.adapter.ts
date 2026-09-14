// Talks to the first target's blob store through its SDK. Reads STORAGE_KEY as the read-write
// token; STORAGE_URL is the public base the store answers on and may stay empty.
import { del, head, put } from "@vercel/blob";
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Storage } from "./contract";

function token(): string {
  if (!env.STORAGE_KEY) {
    throw new Error("STORAGE_KEY is empty: the vercel-blob adapter needs the read-write token");
  }
  return env.STORAGE_KEY;
}

async function locate(key: string): Promise<string | null> {
  try {
    const meta = await head(key, { token: token() });
    return meta.url;
  } catch {
    return null;
  }
}

export function adapter(): Storage {
  const base = env.STORAGE_URL ?? "";
  return {
    put: async (key, bytes, contentType) => {
      await put(key, Buffer.from(bytes), { access: "public", contentType, token: token() });
    },
    get: async (key) => {
      const url = await locate(key);
      if (!url) {
        return null;
      }
      const response = await fetch(url, { signal: withTimeout() });
      if (!response.ok) {
        return null;
      }
      return new Uint8Array(await response.arrayBuffer());
    },
    remove: async (key) => {
      const url = await locate(key);
      if (url) {
        await del(url, { token: token() });
      }
    },
    url: (key) => `${base}/${key}`,
  };
}
