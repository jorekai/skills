import { describe, expect, it } from "vitest";
import { adapter, captured } from "./memory.adapter";

describe("errors port", () => {
  it("captures an error with its context", async () => {
    const errors = adapter();
    const before = captured.length;
    await errors.capture(new Error("boom"), { route: "/api/health" });
    await errors.flush();
    expect(captured).toHaveLength(before + 1);
    expect(captured[captured.length - 1]).toEqual({
      message: "boom",
      context: { route: "/api/health" },
    });
  });
});
