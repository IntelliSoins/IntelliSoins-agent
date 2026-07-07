import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const binPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../bin/prose-pg.mjs");

describe("prose-pg CLI", () => {
  it("prints help without requiring a database URL", () => {
    const result = spawnSync(process.execPath, [binPath, "help"], {
      encoding: "utf8",
      env: {
        ...process.env,
        OPENPROSE_POSTGRES_URL: "",
        OPENPROSE_POSTGRES_USER_URL: "",
        DATABASE_URL: "",
      },
    });
    expect(result.status).toBe(0);
    expect(result.stderr).toContain("prose-pg check");
    expect(result.stderr).toContain("prose-pg batch");
  });
});
