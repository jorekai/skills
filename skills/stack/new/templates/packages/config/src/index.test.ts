import { describe, expect, it } from "vitest";
import { TIMEOUT_MS, withTimeout } from "./index";

describe("withTimeout", () => {
  it("returns a signal that is not yet aborted", () => {
    expect(withTimeout().aborted).toBe(false);
  });

  it("uses the shared timeout by default", () => {
    expect(TIMEOUT_MS).toBeGreaterThan(0);
    expect(withTimeout(TIMEOUT_MS)).toBeInstanceOf(AbortSignal);
  });
});
