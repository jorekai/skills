// Talks to the database through a connection pool in a process that lives. Reads DB_URL as the
// connection string; DB_KEY is unused by this adapter.
import { Pool } from "pg";
import { env } from "@app/env";
import type { Db, Row } from "./contract";

const TABLE =
  "create table if not exists documents (collection text, id text, body jsonb, primary key (collection, id))";

function url(): string {
  if (!env.DB_URL) {
    throw new Error("DB_URL is empty: the pool adapter needs the connection string");
  }
  return env.DB_URL;
}

export function adapter(): Db {
  const pool = new Pool({ connectionString: url() });
  let ready: Promise<void> | null = null;
  const ensure = (): Promise<void> => {
    ready ??= pool.query(TABLE).then(() => undefined);
    return ready;
  };
  return {
    get: async (collection, id) => {
      await ensure();
      const result = await pool.query<{ body: Row }>(
        "select body from documents where collection = $1 and id = $2",
        [collection, id],
      );
      return result.rows[0]?.body ?? null;
    },
    put: async (collection, id, row) => {
      await ensure();
      await pool.query(
        "insert into documents (collection, id, body) values ($1, $2, $3) on conflict (collection, id) do update set body = excluded.body",
        [collection, id, JSON.stringify(row)],
      );
    },
    list: async (collection) => {
      await ensure();
      const result = await pool.query<{ body: Row }>(
        "select body from documents where collection = $1 order by id",
        [collection],
      );
      return result.rows.map((r) => r.body);
    },
    remove: async (collection, id) => {
      await ensure();
      await pool.query("delete from documents where collection = $1 and id = $2", [collection, id]);
    },
    close: async () => {
      await pool.end();
    },
  };
}
