// The route the scheduler calls. The secret in JOBS_KEY is what tells the scheduler from
// anybody else; without it no job runs from outside.
import { env } from "@app/env";
import { jobs } from "@app/ports/jobs";

export async function POST(
  request: Request,
  context: { params: Promise<{ name: string }> },
): Promise<Response> {
  const given = request.headers.get("authorization") ?? "";
  if (!env.JOBS_KEY || given !== `Bearer ${env.JOBS_KEY}`) {
    return new Response("forbidden", { status: 403 });
  }
  const { name } = await context.params;
  await jobs.run(name);
  return Response.json({ ran: name });
}
