import { describe, expect, it } from "vitest";
import { adapter } from "./memory.adapter";

describe("auth port", () => {
  it("issues a token and verifies the subject behind it", async () => {
    const auth = adapter();
    const token = await auth.issue("user-1");
    expect(await auth.verify(token)).toEqual({ subject: "user-1" });
    expect(await auth.verify("not-a-token")).toBeNull();
  });
});
