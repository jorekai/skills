import { describe, expect, it } from "vitest";
import { cn } from "./index";

describe("cn", () => {
  it("joins the parts with one space", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("drops false, undefined and empty parts", () => {
    expect(cn("a", false, undefined, "", "b")).toBe("a b");
  });
});
