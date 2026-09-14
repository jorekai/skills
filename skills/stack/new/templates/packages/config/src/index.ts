// Constants every package may import. A network call takes its time limit from here, so the
// number stands once and the `no-untimed-fetch` rule can name it.
export const TIMEOUT_MS = 10_000;

// A signal that aborts after `ms`, for the `signal` option of every fetch.
export function withTimeout(ms: number = TIMEOUT_MS): AbortSignal {
  return AbortSignal.timeout(ms);
}
