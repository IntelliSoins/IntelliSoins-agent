// Scoped state-dir helpers let multi-account plugins isolate plugin-state SQLite paths.
import path from "node:path";

export type ScopedStateEnvOptions = {
  env?: NodeJS.ProcessEnv;
  stateDir?: string;
  stateRootDir?: string;
  storePath?: string;
};

function resolveStateDirOverride(options: ScopedStateEnvOptions | undefined): string | undefined {
  if (!options) {
    return undefined;
  }
  const stateDir = options.stateDir?.trim();
  if (stateDir) {
    return stateDir;
  }
  const stateRootDir = options.stateRootDir?.trim();
  if (stateRootDir) {
    return stateRootDir;
  }
  const storePath = options.storePath?.trim();
  if (storePath) {
    return path.dirname(storePath);
  }
  return undefined;
}

export function resolveScopedStateEnv(
  options?: ScopedStateEnvOptions,
): NodeJS.ProcessEnv | undefined {
  const stateDir = resolveStateDirOverride(options);
  if (!stateDir) {
    return options?.env;
  }
  return {
    ...(options?.env ?? process.env),
    OPENCLAW_STATE_DIR: stateDir,
  };
}
