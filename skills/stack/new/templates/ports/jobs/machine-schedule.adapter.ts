// Declares jobs as scheduled machines on the third target, one `fly machine run --schedule`
// line per job; the machine calls `/api/jobs/<name>`. The platform's schedule takes hourly,
// daily, weekly or monthly, so the cron string is mapped to the nearest of those. Reads JOBS_URL
// as the app's address and JOBS_KEY as the bearer the route expects.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Handler, Jobs } from "./contract";

const jobs = new Map<string, { cron: string; run: Handler }>();

function base(): string {
  if (!env.JOBS_URL) {
    throw new Error("JOBS_URL is empty: the machine-schedule adapter needs the app's address");
  }
  return env.JOBS_URL.replace(/\/$/, "");
}

// The platform knows four periods. A cron with a fixed day of month is monthly, a fixed day of
// week weekly, a fixed hour daily, everything else hourly.
function period(cron: string): "hourly" | "daily" | "weekly" | "monthly" {
  const [, hour = "*", dayOfMonth = "*", , dayOfWeek = "*"] = cron.split(/\s+/);
  if (dayOfMonth !== "*") {
    return "monthly";
  }
  if (dayOfWeek !== "*") {
    return "weekly";
  }
  return hour === "*" ? "hourly" : "daily";
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
      [...jobs.entries()]
        .map(
          ([name, job]) =>
            `fly machine run curlimages/curl --schedule ${period(job.cron)} -- curl -fsS -X POST -H "Authorization: Bearer $JOBS_KEY" ${url}/api/jobs/${name}`,
        )
        .join("\n"),
  };
}
