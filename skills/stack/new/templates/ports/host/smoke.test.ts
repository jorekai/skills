import { describe, expect, it } from "vitest";
import { adapter } from "./memory.adapter";

describe("host port", () => {
  it("builds a url under its address and reports up", async () => {
    const host = adapter();
    expect(host.url("/api/health")).toBe("http://localhost:3000/api/health");
    expect(host.url("api/health")).toBe(host.url("/api/health"));
    expect(host.healthPath).toBe("/api/health");
    expect(await host.up()).toBe(true);
  });
});
