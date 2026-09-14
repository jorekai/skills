import { describe, expect, it } from "vitest";
import { adapter } from "./memory.adapter";

describe("jobs port", () => {
  it("defines a job and runs it by name", async () => {
    const jobs = adapter();
    let ran = 0;
    jobs.define("nightly", "0 3 * * *", async () => {
      ran += 1;
    });
    expect(jobs.names()).toContain("nightly");
    await jobs.run("nightly");
    expect(ran).toBe(1);
    expect(jobs.manifest()).toBe("");
    await expect(jobs.run("missing")).rejects.toThrow("no job named missing");
  });
});
