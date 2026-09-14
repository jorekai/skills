// Talks to the database through the pooling binding of the worker runtime. Reads DB_URL as the
// pooled connection string the binding hands the worker; DB_KEY names the binding for the
// deploy configuration and is not read here.
import { Client } from "pg";
import { env } from "@app/env";
import type { Db, Row } from "./contract";

const TABLE =
  "create table if not exists documents (collection text, id text, body jsonb, primary key (collection, id))";

function url(): string {
  if (!env.DB_URL) {
    throw new Error("DB_URL is empty: the hyperdrive adapter needs the pooled connection string");
  }
  return env.DB_URL;
}

// A worker holds no long-lived socket, so every call opens one client through the pooling
// binding and closes it again; the binding is what keeps the real connections warm.
async function withClient<T>(run: (client: Client) => Promise<T>): Promise<T> {
  const client = new Client({ connectionString: url() });
  await client.connect();
  try {
    await client.query(TABLE);
    return await run(client);
  } finally {
    await client.end();
  }
}

export function adapter(): Db {
  return {
    get: (collection, id) =>
      withClient(async (client) => {
        const result = await client.query<{ body: Row }>(
          "select body from documents where collection = $1 and id = $2",
          [collection, id],
        );
        return result.rows[0]?.body ?? null;
      }),
    put: (collection, id, row) =>
      withClient(async (client) => {
        await client.query(
          "insert into documents (collection, id, body) values ($1, $2, $3) on conflict (collection, id) do update set body = excluded.body",
          [collection, id, JSON.stringify(row)],
        );
      }),
    list: (collection) =>
      withClient(async (client) => {
        const result = await client.query<{ body: Row }>(
          "select body from documents where collection = $1 order by id",
          [collection],
        );
        return result.rows.map((r) => r.body);
      }),
    remove: (collection, id) =>
      withClient(async (client) => {
        await client.query("delete from documents where collection = $1 and id = $2", [
          collection,
          id,
        ]);
      }),
    close: async () => undefined,
  };
}
