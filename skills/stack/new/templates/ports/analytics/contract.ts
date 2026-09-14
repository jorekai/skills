// The analytics port: one event for one person, and a flush before the process ends. Whose
// server receives it is the adapter's business.
export type Properties = Record<string, string | number | boolean | null>;

export interface Analytics {
  capture(event: string, distinctId: string, properties?: Properties): Promise<void>;
  flush(): Promise<void>;
}
