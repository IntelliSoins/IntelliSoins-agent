import path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveScopedStateEnv } from "./scoped-state-env.js";

describe("resolveScopedStateEnv", () => {
  it("returns env unchanged when no state override is provided", () => {
    const env = { OPENCLAW_STATE_DIR: "/base", FOO: "bar" };
    expect(resolveScopedStateEnv({ env })).toBe(env);
    expect(resolveScopedStateEnv()).toBeUndefined();
  });

  it("overrides OPENCLAW_STATE_DIR from stateDir", () => {
    const env = { OPENCLAW_STATE_DIR: "/base", FOO: "bar" };
    expect(resolveScopedStateEnv({ env, stateDir: "/scoped" })).toEqual({
      OPENCLAW_STATE_DIR: "/scoped",
      FOO: "bar",
    });
  });

  it("overrides OPENCLAW_STATE_DIR from stateRootDir", () => {
    expect(resolveScopedStateEnv({ stateRootDir: "/root" })).toEqual({
      ...process.env,
      OPENCLAW_STATE_DIR: "/root",
    });
  });

  it("overrides OPENCLAW_STATE_DIR from storePath parent", () => {
    const storePath = path.join("/accounts", "acct-1", "state.sqlite");
    expect(resolveScopedStateEnv({ storePath })).toEqual({
      ...process.env,
      OPENCLAW_STATE_DIR: path.join("/accounts", "acct-1"),
    });
  });

  it("prefers stateDir over stateRootDir and storePath", () => {
    expect(
      resolveScopedStateEnv({
        stateDir: "/preferred",
        stateRootDir: "/ignored",
        storePath: "/also/ignored/state.sqlite",
      }),
    ).toEqual({
      ...process.env,
      OPENCLAW_STATE_DIR: "/preferred",
    });
  });
});
