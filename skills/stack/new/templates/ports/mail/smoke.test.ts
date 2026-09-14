import { describe, expect, it } from "vitest";
import { adapter, outbox } from "./memory.adapter";

describe("mail port", () => {
  it("sends a message into the outbox and returns an id", async () => {
    const mail = adapter();
    const before = outbox.length;
    const { id } = await mail.send({ to: "a@example.com", subject: "hi", text: "body" });
    expect(id).toMatch(/^memory-\d+$/);
    expect(outbox).toHaveLength(before + 1);
    expect(outbox[outbox.length - 1]?.to).toBe("a@example.com");
  });
});
