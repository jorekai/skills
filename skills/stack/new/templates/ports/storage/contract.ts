// The storage port: an object store keyed by path. The bytes are the whole value; a content
// type travels with them so a browser can read a public url.
export interface Storage {
  put(key: string, bytes: Uint8Array, contentType: string): Promise<void>;
  get(key: string): Promise<Uint8Array | null>;
  remove(key: string): Promise<void>;
  url(key: string): string;
}
