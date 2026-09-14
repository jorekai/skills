// Declares jobs as the first target's cron entries, which call `/api/jobs/<name>` on schedule.
// Reads JOBS_URL as the address the platform calls and JOBS_KEY as the bearer it must send.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Handler, Jobs } from "./contract";

const jobs = new Map<string, { cron: string; run: Handler }>();

function base(): string {
  if (!env.JOBS_URL) {
    throw new Error(
      "JOBS_URL is empty: the vercel-cron adapter needs the address the platform calls",
    );
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
  base();
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
        {
          crons: [...jobs.entries()].map(([name, job]) => ({
            path: `/api/jobs/${name}`,
            schedule: job.cron,
          })),
        },
        null,
        2,
      ),
  };
}
