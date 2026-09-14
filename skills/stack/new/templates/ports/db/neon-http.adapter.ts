// Talks to the database over HTTP through the serverless driver, for a function that owns no
// socket. Reads DB_URL as the connection string; DB_KEY is unused by this adapter.
import { neon } from "@neondatabase/serverless";
import { env } from "@app/env";
import type { Db, Row } from "./contract";

const TABLE =
  "create table if not exists documents (collection text, id text, body jsonb, primary key (collection, id))";

function url(): string {
  if (!env.DB_URL) {
    throw new Error("DB_URL is empty: the neon-http adapter needs the connection string");
  }
  return env.DB_URL;
}

export function adapter(): Db {
  const sql = neon(url());
  let ready: Promise<void> | null = null;
  const ensure = (): Promise<void> => {
    ready ??= sql.query(TABLE).then(() => undefined);
    return ready;
  };
  return {
    get: async (collection, id) => {
      await ensure();
      const rows = await sql.query("select body from documents where collection = $1 and id = $2", [
        collection,
        id,
      ]);
      const first = rows[0];
      return first ? (first["body"] as Row) : null;
    },
    put: async (collection, id, row) => {
      await ensure();
      await sql.query(
        "insert into documents (collection, id, body) values ($1, $2, $3) on conflict (collection, id) do update set body = excluded.body",
        [collection, id, JSON.stringify(row)],
      );
    },
    list: async (collection) => {
      await ensure();
      const rows = await sql.query("select body from documents where collection = $1 order by id", [
        collection,
      ]);
      return rows.map((r) => r["body"] as Row);
    },
    remove: async (collection, id) => {
      await ensure();
      await sql.query("delete from documents where collection = $1 and id = $2", [collection, id]);
    },
    close: async () => undefined,
  };
}
