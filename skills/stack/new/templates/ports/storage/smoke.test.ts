import { describe, expect, it } from "vitest";
import { adapter } from "./memory.adapter";

describe("storage port", () => {
  it("stores bytes and reads them back", async () => {
    const storage = adapter();
    const bytes = new TextEncoder().encode("hello");
    await storage.put("a/b.txt", bytes, "text/plain");
    expect(await storage.get("a/b.txt")).toEqual(bytes);
    expect(storage.url("a/b.txt")).toContain("a/b.txt");
    await storage.remove("a/b.txt");
    expect(await storage.get("a/b.txt")).toBeNull();
  });
});
