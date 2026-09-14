import { describe, expect, it } from "vitest";
import { adapter, events } from "./memory.adapter";

describe("analytics port", () => {
  it("captures an event for a person", async () => {
    const analytics = adapter();
    const before = events.length;
    await analytics.capture("signed_up", "user-1", { plan: "free" });
    await analytics.flush();
    expect(events).toHaveLength(before + 1);
    expect(events[events.length - 1]).toEqual({
      event: "signed_up",
      distinctId: "user-1",
      properties: { plan: "free" },
    });
  });
});
