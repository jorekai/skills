// The db port: a document store keyed by collection and id. Every adapter, offline or wired,
// implements exactly this, so the app never sees a driver.
export type Row = Record<string, unknown>;

export interface Db {
  get(collection: string, id: string): Promise<Row | null>;
  put(collection: string, id: string, row: Row): Promise<void>;
  list(collection: string): Promise<Row[]>;
  remove(collection: string, id: string): Promise<void>;
  close(): Promise<void>;
}
