// The offline db adapter: rows in a map, nothing on disk, nothing on the network. It reads no key.
import type { Db, Row } from "./contract";

const store = new Map<string, Map<string, Row>>();

function collectionOf(name: string): Map<string, Row> {
  let rows = store.get(name);
  if (!rows) {
    rows = new Map<string, Row>();
    store.set(name, rows);
  }
  return rows;
}

export function adapter(): Db {
  return {
    get: async (collection, id) => collectionOf(collection).get(id) ?? null,
    put: async (collection, id, row) => {
      collectionOf(collection).set(id, { ...row });
    },
    list: async (collection) => [...collectionOf(collection).values()],
    remove: async (collection, id) => {
      collectionOf(collection).delete(id);
    },
    close: async () => {
      store.clear();
    },
  };
}
