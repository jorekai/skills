// Declares jobs as systemd timer units on a host the project runs, one timer per job whose
// service calls `/api/jobs/<name>`. Reads JOBS_URL as the app's address and JOBS_KEY as the
// bearer the route expects.
import { withTimeout } from "@app/config";
import { env } from "@app/env";
import type { Handler, Jobs } from "./contract";

const jobs = new Map<string, { cron: string; run: Handler }>();

function base(): string {
  if (!env.JOBS_URL) {
    throw new Error("JOBS_URL is empty: the systemd-timer adapter needs the app's address");
  }
  return env.JOBS_URL.replace(/\/$/, "");
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// The four cron fields this adapter reads, each with the value a missing field carries.
function fields(cron: string): { minute: string; hour: string; day: string; weekday: string } {
  const parts = cron.split(/\s+/);
  return {
    minute: parts[0] || "0",
    hour: parts[1] || "*",
    day: parts[2] || "*",
    weekday: parts[4] || "*",
  };
}

// systemd's calendar form: `*-*-* HH:MM:00` for a daily cron, `*-*-* *:MM:00` for an hourly one,
// and the weekday or day of month in front where the cron fixes one.
function onCalendar(cron: string): string {
  const { minute, hour, day, weekday } = fields(cron);
  const prefix = weekday === "*" ? "" : `${DAYS[Number(weekday) % 7] ?? "Mon"} `;
  const dd = day === "*" ? "*" : day.padStart(2, "0");
  const hh = hour === "*" ? "*" : hour.padStart(2, "0");
  return `${prefix}*-*-${dd} ${hh}:${minute.padStart(2, "0")}:00`;
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

function unit(name: string, cron: string, url: string): string {
  return [
    `# /etc/systemd/system/app-${name}.timer`,
    "[Timer]",
    `OnCalendar=${onCalendar(cron)}`,
    "Persistent=true",
    "[Install]",
    "WantedBy=timers.target",
    "",
    `# /etc/systemd/system/app-${name}.service`,
    "[Service]",
    "Type=oneshot",
    "EnvironmentFile=/srv/app/.env",
    `ExecStart=/usr/bin/curl -fsS -X POST -H "Authorization: Bearer $JOBS_KEY" ${url}/api/jobs/${name}`,
  ].join("\n");
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
      [...jobs.entries()].map(([name, job]) => unit(name, job.cron, url)).join("\n\n"),
  };
}
