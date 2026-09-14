// Types for the declaration reader, so a config file written in TypeScript can import it.
export interface Stack {
  name: string;
  oss_level: string;
  target: string;
  runtime: Record<string, string>;
  ports: Record<string, string>;
  gates: Record<string, number | string>;
  guards: Record<string, string>;
  enforcement: string[];
  workspaces: Record<string, string[]>;
  rules: string[];
  waivers: Array<Record<string, string | number>>;
  [key: string]: unknown;
}
export function parseYaml(text: string): unknown;
export function readStack(root?: string): Stack;
export function get(value: unknown, dotted: string): unknown;
