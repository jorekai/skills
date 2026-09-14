// The mail port: one message out, one id back. Whose delivery carries it is the adapter's business.
export interface Message {
  to: string;
  subject: string;
  text: string;
}

export interface Mail {
  send(message: Message): Promise<{ id: string }>;
}
