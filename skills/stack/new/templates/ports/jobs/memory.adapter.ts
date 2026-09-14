// The offline jobs adapter: handlers in a map, run when asked, no scheduler declared. It reads
// no key.
import type { Handler, Jobs } from "./contract";

const jobs = new Map<string, { cron: string; run: Handler }>();

export function adapter(): Jobs {
  return {
    define: (name, cron, run) => {
      jobs.set(name, { cron, run });
    },
    names: () => [...jobs.keys()],
    run: async (name) => {
      const job = jobs.get(name);
      if (!job) {
        throw new Error(`no job named ${name}; defined: ${[...jobs.keys()].join(", ") || "none"}`);
      }
      await job.run();
    },
    manifest: () => "",
  };
}
