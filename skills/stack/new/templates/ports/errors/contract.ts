// The errors port: one caught error with its context, and a flush before the process ends.
// Whose server receives it is the adapter's business.
export type Context = Record<string, string | number | boolean | null>;

export interface Errors {
  capture(error: unknown, context?: Context): Promise<void>;
  flush(): Promise<void>;
}
