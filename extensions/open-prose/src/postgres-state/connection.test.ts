import { describe, expect, it } from "vitest";
import { resolveOpenProsePostgresUrl, requireOpenProsePostgresUrl } from "./connection.js";

describe("resolveOpenProsePostgresUrl", () => {
  it("prefers OPENPROSE_POSTGRES_URL", () => {
    expect(
      resolveOpenProsePostgresUrl({
        OPENPROSE_POSTGRES_URL: "postgres://primary",
        OPENPROSE_POSTGRES_USER_URL: "postgres://user",
        DATABASE_URL: "postgres://fallback",
      }),
    ).toBe("postgres://primary");
  });

  it("falls back through documented precedence", () => {
    expect(
      resolveOpenProsePostgresUrl({
        OPENPROSE_POSTGRES_USER_URL: "postgres://user",
        DATABASE_URL: "postgres://fallback",
      }),
    ).toBe("postgres://user");
    expect(resolveOpenProsePostgresUrl({ DATABASE_URL: "postgres://fallback" })).toBe(
      "postgres://fallback",
    );
  });

  it("throws when no URL is configured", () => {
    expect(() => requireOpenProsePostgresUrl({})).toThrow(/missing postgresql url/i);
  });
});
