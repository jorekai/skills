// The env schema: two keys per port, sixteen in all, every one optional. A port whose two keys
// are both empty resolves to its memory adapter. The names here are the names in .env.example.
import { z } from "zod";

export const PORTS = [
  "db",
  "storage",
  "jobs",
  "host",
  "auth",
  "mail",
  "analytics",
  "errors",
] as const;
export type Port = (typeof PORTS)[number];

const key = z.string().optional();

export const schema = z.object({
  DB_URL: key,
  DB_KEY: key,
  STORAGE_URL: key,
  STORAGE_KEY: key,
  JOBS_URL: key,
  JOBS_KEY: key,
  HOST_URL: key,
  HOST_KEY: key,
  AUTH_URL: key,
  AUTH_KEY: key,
  MAIL_URL: key,
  MAIL_KEY: key,
  ANALYTICS_URL: key,
  ANALYTICS_KEY: key,
  ERRORS_URL: key,
  ERRORS_KEY: key,
});

export type Env = z.infer<typeof schema>;

// The two keys of a port, as names into the schema.
export function keysOf(port: Port): [keyof Env, keyof Env] {
  const upper = port.toUpperCase();
  return [`${upper}_URL` as keyof Env, `${upper}_KEY` as keyof Env];
}
