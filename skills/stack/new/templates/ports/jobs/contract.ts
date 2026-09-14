// The jobs port: named handlers on a cron schedule. The runtime's own scheduler calls the route
// `/api/jobs/<name>`; the adapter says how that schedule is declared for its platform.
export type Handler = () => Promise<void>;

export interface Jobs {
  define(name: string, cron: string, run: Handler): void;
  names(): string[];
  run(name: string): Promise<void>;
  manifest(): string;
}
