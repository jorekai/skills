import { describe, expect, it } from "vitest";
import { PORTS, keysOf, resolve, schema } from "./index";

describe("the env schema", () => {
  it("parses an empty environment, so the gate is green before any account exists", () => {
    expect(schema.parse({})).toEqual({});
  });

  it("names two keys per port", () => {
    for (const port of PORTS) {
      const [url, key] = keysOf(port);
      expect(url).toBe(`${port.toUpperCase()}_URL`);
      expect(key).toBe(`${port.toUpperCase()}_KEY`);
      expect(schema.shape).toHaveProperty(url);
      expect(schema.shape).toHaveProperty(key);
    }
  });

  it("resolves a port to memory while both keys are empty, and to wired once one is set", () => {
    expect(resolve({}, "db")).toBe("memory");
    expect(resolve({ DB_URL: "" }, "db")).toBe("memory");
    expect(resolve({ DB_URL: "postgres://x" }, "db")).toBe("wired");
    expect(resolve({ STORAGE_KEY: "k" }, "storage")).toBe("wired");
  });
});
