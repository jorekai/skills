// Talks to any store that speaks the S3 protocol, including one the project runs itself:
// path-style addressing and the region from the `region` query parameter, `us-east-1` when
// none. Reads STORAGE_URL as `s3://<bucket>@<endpoint>` and STORAGE_KEY as `<access key id>:<secret>`.
import {
  DeleteObjectCommand,
  GetObjectCommand,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { env } from "@app/env";
import type { Storage } from "./contract";

// The two halves of STORAGE_KEY, refused when either is empty.
function credentials(): [string, string] {
  if (!env.STORAGE_URL || !env.STORAGE_KEY) {
    throw new Error("STORAGE_URL or STORAGE_KEY is empty: the s3 adapter needs both");
  }
  const [id, secret] = env.STORAGE_KEY.split(":");
  if (!id || !secret) {
    throw new Error("STORAGE_URL reads s3://<bucket>@<endpoint> and STORAGE_KEY <id>:<secret>");
  }
  return [id, secret];
}

function target(): {
  bucket: string;
  endpoint: string;
  region: string;
  id: string;
  secret: string;
} {
  const [id, secret] = credentials();
  const match = /^s3:\/\/([^@]+)@([^?]+)(?:\?region=([^&]+))?$/.exec(env.STORAGE_URL ?? "");
  if (!match || !match[1] || !match[2]) {
    throw new Error("STORAGE_URL reads s3://<bucket>@<endpoint> and STORAGE_KEY <id>:<secret>");
  }
  const host = match[2];
  const endpoint = host.startsWith("http") ? host : `https://${host}`;
  return { bucket: match[1], endpoint, region: match[3] ?? "us-east-1", id, secret };
}

export function adapter(): Storage {
  const t = target();
  const client = new S3Client({
    region: t.region,
    endpoint: t.endpoint,
    forcePathStyle: true,
    credentials: { accessKeyId: t.id, secretAccessKey: t.secret },
  });
  return {
    put: async (key, bytes, contentType) => {
      await client.send(
        new PutObjectCommand({ Bucket: t.bucket, Key: key, Body: bytes, ContentType: contentType }),
      );
    },
    get: async (key) => {
      try {
        const out = await client.send(new GetObjectCommand({ Bucket: t.bucket, Key: key }));
        return out.Body ? await out.Body.transformToByteArray() : null;
      } catch {
        return null;
      }
    },
    remove: async (key) => {
      await client.send(new DeleteObjectCommand({ Bucket: t.bucket, Key: key }));
    },
    url: (key) => `${t.endpoint}/${t.bucket}/${key}`,
  };
}
