// The offline host adapter: a local address, always up, no network. It reads no key.
import type { Host } from "./contract";

export function adapter(): Host {
  return {
    name: "memory",
    healthPath: "/api/health",
    url: (path) => `http://localhost:3000${path.startsWith("/") ? path : `/${path}`}`,
    up: async () => true,
  };
}
