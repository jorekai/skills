// The auth port: a token for a subject, and the subject behind a token. Whose identity store
// answers is the adapter's business.
export interface Session {
  subject: string;
}

export interface Auth {
  issue(subject: string): Promise<string>;
  verify(token: string): Promise<Session | null>;
}
