// The one place that reads the environment. Every other file imports `env` from here, and the
// `no-raw-env` rule names this package as the allowed state.
import { keysOf, schema, type Env, type Port } from "./schema";

export { PORTS, keysOf, schema, type Env, type Port } from "./schema";

export const env: Env = schema.parse(process.env);

export type Resolution = "memory" | "wired";

// Which adapter a port resolves to for these values: memory while both keys are empty.
export function resolve(values: Env, port: Port): Resolution {
  const [url, key] = keysOf(port);
  return values[url] || values[key] ? "wired" : "memory";
}

export function adapterOf(port: Port): Resolution {
  return resolve(env, port);
}
