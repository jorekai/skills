import { describe, expect, it } from "vitest";
import { adapter } from "./memory.adapter";

describe("db port", () => {
  it("stores a row and reads it back", async () => {
    const db = adapter();
    await db.put("users", "u1", { name: "a" });
    expect(await db.get("users", "u1")).toEqual({ name: "a" });
    expect(await db.list("users")).toHaveLength(1);
    await db.remove("users", "u1");
    expect(await db.get("users", "u1")).toBeNull();
    await db.close();
  });
});
