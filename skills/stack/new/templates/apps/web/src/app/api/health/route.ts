// What each port resolved to. The browser test reads this, and so does a person who wants to
// know whether the app runs on memory adapters or on accounts.
import { PORTS, adapterOf } from "@app/env";

export function GET(): Response {
  const ports = Object.fromEntries(PORTS.map((port) => [port, adapterOf(port)]));
  return Response.json({ ok: true, ports });
}
