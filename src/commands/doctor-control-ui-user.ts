import { password as clackPassword, text as clackText } from "@clack/prompts";
import { note } from "../../packages/terminal-core/src/note.js";
import { stylePromptMessage } from "../../packages/terminal-core/src/prompt-style.js";
import type { OpenClawConfig } from "../config/config.js";
import {
  confirmControlUiUserTotpEnrollment,
  createControlUiUser,
} from "../gateway/control-ui-users.sqlite.js";
import type { RuntimeEnv } from "../runtime.js";
// Doctor flow for bootstrapping the first Control UI operator account with MFA.
import { buildTotpOtpauthUri } from "../security/totp.js";
import { verifyTotpCode } from "../security/totp.js";
import { guardCancel } from "./onboard-helpers.js";

export type DoctorControlUiUserOptions = {
  username?: string;
  password?: string;
  mfaCode?: string;
  nonInteractive?: boolean;
  yes?: boolean;
};

/** Create the first Control UI user and enroll MFA during doctor. */
export async function runDoctorCreateControlUiUser(params: {
  cfg: OpenClawConfig;
  runtime: RuntimeEnv;
  options: DoctorControlUiUserOptions;
}): Promise<OpenClawConfig> {
  const { runtime, options } = params;
  let cfg = params.cfg;
  const username =
    options.username?.trim() ||
    (options.nonInteractive
      ? ""
      : guardCancel(
          await clackText({
            message:
              stylePromptMessage("Nom d'utilisateur (Control UI)") ??
              "Nom d'utilisateur (Control UI)",
            initialValue: "admin",
          }),
          runtime,
        ));
  if (!username) {
    throw new Error("Control UI username is required.");
  }
  const passwordValue =
    options.password ||
    (options.nonInteractive
      ? ""
      : guardCancel(
          await clackPassword({
            message:
              stylePromptMessage("Mot de passe (min. 12 caractères)") ??
              "Mot de passe (min. 12 caractères)",
          }),
          runtime,
        ));
  if (!passwordValue) {
    throw new Error("Control UI password is required.");
  }
  const created = createControlUiUser({
    username,
    password: passwordValue,
    enrollTotp: true,
  });
  if (!created.totpSecret || !created.totpOtpauthUri) {
    throw new Error("Control UI MFA enrollment failed.");
  }
  note(
    [
      "Scannez ce secret MFA dans votre application d'authentification :",
      created.totpSecret,
      "",
      "URI otpauth :",
      created.totpOtpauthUri,
      "",
      buildTotpOtpauthUri({
        issuer: "IntelliSoins",
        accountName: username,
        secret: created.totpSecret,
      }),
    ].join("\n"),
    "MFA TOTP",
  );
  const confirmCode =
    options.mfaCode?.trim() ||
    (options.nonInteractive
      ? ""
      : guardCancel(
          await clackText({
            message:
              stylePromptMessage(
                "Saisissez le code MFA à 6 chiffres pour confirmer l'inscription",
              ) ?? "Saisissez le code MFA à 6 chiffres pour confirmer l'inscription",
          }),
          runtime,
        ));
  if (!confirmCode) {
    throw new Error("MFA confirmation code is required before enabling users mode.");
  }
  confirmControlUiUserTotpEnrollment({
    username,
    totpCode: confirmCode,
    verifyTotp: verifyTotpCode,
  });
  note("MFA activée pour ce compte.", "Control UI");
  cfg = {
    ...cfg,
    gateway: {
      ...cfg.gateway,
      auth: {
        ...cfg.gateway?.auth,
        mode: "users",
      },
    },
  };
  note(`Compte Control UI "${username}" créé. gateway.auth.mode défini sur "users".`, "Control UI");
  return cfg;
}
