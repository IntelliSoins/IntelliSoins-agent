// Resolves OpenProse PostgreSQL connection URLs from env precedence documented in postgres.md.
export function resolveOpenProsePostgresUrl(env: NodeJS.ProcessEnv = process.env): string {
  return (
    env.OPENPROSE_POSTGRES_URL?.trim() ||
    env.OPENPROSE_POSTGRES_USER_URL?.trim() ||
    env.DATABASE_URL?.trim() ||
    ""
  );
}

export function requireOpenProsePostgresUrl(env: NodeJS.ProcessEnv = process.env): string {
  const url = resolveOpenProsePostgresUrl(env);
  if (!url) {
    throw new Error(
      "Missing PostgreSQL URL. Set OPENPROSE_POSTGRES_URL, OPENPROSE_POSTGRES_USER_URL, or DATABASE_URL.",
    );
  }
  return url;
}
