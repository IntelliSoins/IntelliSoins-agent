import type { OpenClawConfig } from "../config/config.js";
import {
  confirmControlUiUserTotpEnrollment,
  createControlUiUser,
} from "../gateway/control-ui-users.sqlite.js";
// Doctor flow for bootstrapping the first Control UI operator account with MFA.
import { buildTotpOtpauthUri } from "../security/totp.js";
import { verifyTotpCode } from "../security/totp.js";

export type DoctorControlUiUserOptions = {
  username?: string;
  password?: string;
  mfaCode?: string;
  nonInteractive?: boolean;
  yes?: boolean;
};

type DoctorPrompter = {
  note: (message: string, title?: string) => void;
  text: (params: { message: string; initialValue?: string }) => Promise<string>;
  password: (params: { message: string }) => Promise<string>;
  confirm: (params: { message: string; initialValue?: boolean }) => Promise<boolean>;
};

/** Create the first Control UI user and enroll MFA during doctor. */
export async function runDoctorCreateControlUiUser(params: {
  cfg: OpenClawConfig;
  prompter: DoctorPrompter;
  options: DoctorControlUiUserOptions;
}): Promise<OpenClawConfig> {
  const { prompter, options } = params;
  let cfg = params.cfg;
  const username =
    options.username?.trim() ||
    (options.nonInteractive
      ? ""
      : await prompter.text({
          message: "Nom d'utilisateur (Control UI)",
          initialValue: "admin",
        }));
  if (!username) {
    throw new Error("Control UI username is required.");
  }
  const password =
    options.password ||
    (options.nonInteractive
      ? ""
      : await prompter.password({
          message: "Mot de passe (min. 12 caractères)",
        }));
  if (!password) {
    throw new Error("Control UI password is required.");
  }
  const created = createControlUiUser({
    username,
    password,
    enrollTotp: true,
  });
  if (!created.totpSecret || !created.totpOtpauthUri) {
    throw new Error("Control UI MFA enrollment failed.");
  }
  prompter.note(
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
      : await prompter.text({
          message: "Saisissez le code MFA à 6 chiffres pour confirmer l'inscription",
        }));
  if (!confirmCode) {
    throw new Error("MFA confirmation code is required before enabling users mode.");
  }
  confirmControlUiUserTotpEnrollment({
    username,
    totpCode: confirmCode,
    verifyTotp: verifyTotpCode,
  });
  prompter.note("MFA activée pour ce compte.", "Control UI");
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
  prompter.note(
    `Compte Control UI "${username}" créé. gateway.auth.mode défini sur "users".`,
    "Control UI",
  );
  return cfg;
}
