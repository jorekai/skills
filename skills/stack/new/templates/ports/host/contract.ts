// The host port: where the app runs. The adapter knows the public address, the path the platform
// checks for health, and can ask the running app whether it is up.
export interface Host {
  name: string;
  healthPath: string;
  url(path: string): string;
  up(): Promise<boolean>;
}
