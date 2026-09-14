// Declares jobs as the fifth target's cron schedule on a service, one service per job that
// calls `/api/jobs/<name>` and exits. Reads JOBS_URL as the app's address and JOBS_KEY as the
// bearer the route expects.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Handler, Jobs } from "./contract";

const jobs = new Map<string, { cron: string; run: Handler }>();

function base(): string {
  if (!env.JOBS_URL) {
    throw new Error("JOBS_URL is empty: the railway-cron adapter needs the app's address");
  }
  return env.JOBS_URL.replace(/\/$/, "");
}

async function trigger(name: string): Promise<void> {
  const response = await fetch(`${base()}/api/jobs/${name}`, {
    method: "POST",
    headers: { authorization: `Bearer ${env.JOBS_KEY ?? ""}` },
    signal: withTimeout(),
  });
  if (!response.ok) {
    throw new Error(`job ${name} answered ${response.status} at ${base()}`);
  }
}

export function adapter(): Jobs {
  const url = base();
  return {
    define: (name, cron, run) => {
      jobs.set(name, { cron, run });
    },
    names: () => [...jobs.keys()],
    run: async (name) => {
      const job = jobs.get(name);
      if (job) {
        await job.run();
        return;
      }
      await trigger(name);
    },
    manifest: () =>
      JSON.stringify(
        [...jobs.entries()].map(([name, job]) => ({
          service: `${name}-job`,
          cronSchedule: job.cron,
          startCommand: `curl -fsS -X POST -H "Authorization: Bearer $JOBS_KEY" ${url}/api/jobs/${name}`,
        })),
        null,
        2,
      ),
  };
}
