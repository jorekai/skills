// The entry point of the {{PORT}} port. Another package imports `@app/ports/{{PORT}}` and gets
// the offline adapter while both keys of the port are empty, the wired one otherwise.
import { adapterOf } from "@app/env";
import type { {{Port}} } from "./contract";
import { adapter as memory } from "./memory.adapter";
import { wired } from "./wired";

export const {{PORT}}: {{Port}} = adapterOf("{{PORT}}") === "memory" ? memory() : wired();
export type { {{Port}} } from "./contract";
