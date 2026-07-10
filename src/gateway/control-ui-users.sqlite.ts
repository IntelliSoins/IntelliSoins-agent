// Control UI user account persistence in the shared OpenClaw state database.
import { randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import { normalizeLowercaseStringOrEmpty } from "@openclaw/normalization-core/string-coerce";
import type { Insertable, Selectable } from "kysely";
import {
  executeSqliteQuerySync,
  executeSqliteQueryTakeFirstSync,
  getNodeSqliteKysely,
} from "../infra/kysely-sync.js";
import { hashPassword, verifyPassword } from "../security/password-hash.js";
import { decryptTotpSecret, encryptTotpSecret } from "../security/totp-secret-crypto.js";
import { generateTotpSecret } from "../security/totp.js";
import type { DB as OpenClawStateKyselyDatabase } from "../state/openclaw-state-db.generated.js";
import {
  openOpenClawStateDatabase,
  runOpenClawStateWriteTransaction,
  type OpenClawStateDatabaseOptions,
} from "../state/openclaw-state-db.js";

type ControlUiUsersTable = OpenClawStateKyselyDatabase["control_ui_users"];
type ControlUiUserRow = Selectable<ControlUiUsersTable>;

export type ControlUiUserRecord = {
  userId: string;
  username: string;
  passwordHash: string;
  totpSecretEncrypted: string | null;
  totpEnabled: boolean;
  createdAtMs: number;
  updatedAtMs: number;
};

export type CreateControlUiUserInput = {
  username: string;
  password: string;
  enrollTotp?: boolean;
  env?: NodeJS.ProcessEnv;
};

export type CreateControlUiUserResult = {
  user: ControlUiUserRecord;
  totpSecret?: string;
  totpOtpauthUri?: string;
};

function normalizeUsername(username: string): string {
  return normalizeLowercaseStringOrEmpty(username.trim());
}

function mapRow(row: ControlUiUserRow): ControlUiUserRecord {
  return {
    userId: row.user_id,
    username: row.username,
    passwordHash: row.password_hash,
    totpSecretEncrypted: row.totp_secret_encrypted,
    totpEnabled: row.totp_enabled === 1,
    createdAtMs: row.created_at_ms,
    updatedAtMs: row.updated_at_ms,
  };
}

function getUsersKysely(db: DatabaseSync) {
  return getNodeSqliteKysely<Pick<OpenClawStateKyselyDatabase, "control_ui_users">>(db);
}

/** Return true when at least one Control UI user account exists. */
export function hasControlUiUsers(options: OpenClawStateDatabaseOptions = {}): boolean {
  const { db } = openOpenClawStateDatabase(options);
  const kysely = getUsersKysely(db);
  const row = executeSqliteQueryTakeFirstSync(
    db,
    kysely.selectFrom("control_ui_users").select((eb) => eb.fn.countAll<number>().as("count")),
  );
  return Number(row?.count ?? 0) > 0;
}

/** Count Control UI user accounts. */
export function countControlUiUsers(options: OpenClawStateDatabaseOptions = {}): number {
  const { db } = openOpenClawStateDatabase(options);
  const kysely = getUsersKysely(db);
  const row = executeSqliteQueryTakeFirstSync(
    db,
    kysely.selectFrom("control_ui_users").select((eb) => eb.fn.countAll<number>().as("count")),
  );
  return Number(row?.count ?? 0);
}

/** Look up a user by normalized username. */
export function findControlUiUserByUsername(
  username: string,
  options: OpenClawStateDatabaseOptions = {},
): ControlUiUserRecord | null {
  const normalized = normalizeUsername(username);
  if (!normalized) {
    return null;
  }
  const { db } = openOpenClawStateDatabase(options);
  const kysely = getUsersKysely(db);
  const row = executeSqliteQueryTakeFirstSync(
    db,
    kysely.selectFrom("control_ui_users").selectAll().where("username", "=", normalized),
  );
  return row ? mapRow(row) : null;
}

/** Decrypt the stored TOTP secret for a user when MFA is enabled. */
export function resolveControlUiUserTotpSecret(
  user: ControlUiUserRecord,
  env?: NodeJS.ProcessEnv,
): string | null {
  if (!user.totpEnabled || !user.totpSecretEncrypted) {
    return null;
  }
  return decryptTotpSecret(user.totpSecretEncrypted, env);
}

/** Create a new Control UI user with optional TOTP enrollment material. */
export function createControlUiUser(
  input: CreateControlUiUserInput,
  options: OpenClawStateDatabaseOptions = {},
): CreateControlUiUserResult {
  const username = normalizeUsername(input.username);
  if (!username || username.length < 2) {
    throw new Error("Control UI username must be at least 2 characters.");
  }
  if (!input.password || input.password.length < 8) {
    throw new Error("Control UI password must be at least 8 characters.");
  }
  const now = Date.now();
  const userId = randomUUID();
  const passwordHash = hashPassword(input.password);
  let totpSecret: string | undefined;
  let totpSecretEncrypted: string | null = null;
  let totpEnabled = 0;
  if (input.enrollTotp === true) {
    totpSecret = generateTotpSecret();
    totpSecretEncrypted = encryptTotpSecret(totpSecret, input.env);
    totpEnabled = 0;
  }
  const values: Insertable<ControlUiUsersTable> = {
    user_id: userId,
    username,
    password_hash: passwordHash,
    totp_secret_encrypted: totpSecretEncrypted,
    totp_enabled: totpEnabled,
    created_at_ms: now,
    updated_at_ms: now,
  };
  return runOpenClawStateWriteTransaction(options, (db) => {
    const kysely = getUsersKysely(db);
    const existing = executeSqliteQueryTakeFirstSync(
      db,
      kysely.selectFrom("control_ui_users").select("user_id").where("username", "=", username),
    );
    if (existing) {
      throw new Error(`Control UI user "${username}" already exists.`);
    }
    executeSqliteQuerySync(db, kysely.insertInto("control_ui_users").values(values));
    const inserted = executeSqliteQueryTakeFirstSync(
      db,
      kysely.selectFrom("control_ui_users").selectAll().where("user_id", "=", userId),
    );
    if (!inserted) {
      throw new Error("Failed to create Control UI user.");
    }
    const user = mapRow(inserted);
    return {
      user,
      ...(totpSecret
        ? {
            totpSecret,
            totpOtpauthUri: `otpauth://totp/IntelliSoins:${encodeURIComponent(username)}?secret=${encodeURIComponent(totpSecret)}&issuer=IntelliSoins&algorithm=SHA1&digits=6&period=30`,
          }
        : {}),
    };
  });
}

/** Confirm TOTP enrollment by validating the first code and enabling MFA. */
export function confirmControlUiUserTotpEnrollment(
  params: {
    username: string;
    totpCode: string;
    verifyTotp: (secret: string, code: string) => boolean;
    env?: NodeJS.ProcessEnv;
  },
  options: OpenClawStateDatabaseOptions = {},
): ControlUiUserRecord {
  const user = findControlUiUserByUsername(params.username, options);
  if (!user) {
    throw new Error("Control UI user not found.");
  }
  if (user.totpEnabled) {
    throw new Error("Control UI MFA is already enabled for this user.");
  }
  if (!user.totpSecretEncrypted) {
    throw new Error("Control UI MFA enrollment was not started for this user.");
  }
  const secret = decryptTotpSecret(user.totpSecretEncrypted, params.env);
  if (!secret || !params.verifyTotp(secret, params.totpCode)) {
    throw new Error("Invalid MFA confirmation code.");
  }
  const now = Date.now();
  return runOpenClawStateWriteTransaction(options, (db) => {
    const kysely = getUsersKysely(db);
    executeSqliteQuerySync(
      db,
      kysely
        .updateTable("control_ui_users")
        .set({ totp_enabled: 1, updated_at_ms: now })
        .where("user_id", "=", user.userId),
    );
    return { ...user, totpEnabled: true, updatedAtMs: now };
  });
}

/** Verify a username/password pair against stored credentials. */
export function verifyControlUiUserPassword(
  username: string,
  password: string,
  options: OpenClawStateDatabaseOptions = {},
): ControlUiUserRecord | null {
  const user = findControlUiUserByUsername(username, options);
  if (!user) {
    return null;
  }
  return verifyPassword(password, user.passwordHash) ? user : null;
}
