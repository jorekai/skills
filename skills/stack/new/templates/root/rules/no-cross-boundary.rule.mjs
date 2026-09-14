// An import crosses an edge only where `workspaces` in stack.yaml names it. The message names
// the packages this workspace may import, so the fix is a line, not a guess.
export default {
  id: "no-cross-boundary",
  kind: "edge",
  files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"],
  waivable: "boundary",
  message: "{file}:{line} imports {found}; allowed from this workspace: {allowed}",
};
