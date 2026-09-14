// Shared code without a framework. The app imports this; this imports @app/config and nothing
// else, which is the edge `workspaces` in stack.yaml allows.

// Class names joined, with the falsy parts dropped.
export function cn(...parts: Array<string | false | undefined>): string {
  return parts.filter((p): p is string => typeof p === "string" && p.length > 0).join(" ");
}
