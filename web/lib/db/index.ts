/**
 * Neon HTTP-driver Drizzle client. The HTTP driver issues one fetch per query
 * (no persistent connections) so it's safe on Vercel serverless/edge without
 * exhausting Postgres connections. Point DATABASE_URL at the POOLED Neon host.
 *
 * Lazy-initialized: importing this module never connects or throws, so
 * `next build` can collect routes without a live DATABASE_URL. The error
 * surfaces only on first actual query at request time.
 */
import { neon } from "@neondatabase/serverless";
import { drizzle, type NeonHttpDatabase } from "drizzle-orm/neon-http";

import * as schema from "./schema";

let _db: NeonHttpDatabase<typeof schema> | null = null;

function getDb(): NeonHttpDatabase<typeof schema> {
  if (_db) return _db;
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set. Provision Neon (Vercel Marketplace) and pull envs.");
  }
  _db = drizzle(neon(url), { schema, casing: "snake_case" });
  return _db;
}

// Proxy so callers can `import { db }` and use it directly; init happens on first use.
export const db = new Proxy({} as NeonHttpDatabase<typeof schema>, {
  get(_target, prop, receiver) {
    return Reflect.get(getDb(), prop, receiver);
  },
});

export { schema };
