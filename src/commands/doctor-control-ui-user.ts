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
  nonInteractive?: boolean;
  yes?: boolean;
};

type DoctorPrompter = {
  note: (message: string, title?: string) => void;
  text: (params: { message: string; initialValue?: string }) => Promise<string>;
  password: (params: { message: string }) => Promise<string>;
  confirm: (params: { message: string; initialValue?: boolean }) => Promise<boolean>;
};

/** Create the first Control UI user and optionally enroll MFA during doctor. */
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
          message: "Mot de passe (min. 8 caractères)",
        }));
  if (!password) {
    throw new Error("Control UI password is required.");
  }
  const enrollTotp =
    options.nonInteractive === true
      ? options.yes === true
      : await prompter.confirm({
          message: "Configurer l'authentification MFA (TOTP) maintenant ?",
          initialValue: true,
        });
  const created = createControlUiUser({
    username,
    password,
    enrollTotp,
  });
  if (enrollTotp && created.totpSecret && created.totpOtpauthUri) {
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
    const confirmCode = options.nonInteractive
      ? ""
      : await prompter.text({
          message: "Saisissez le code MFA à 6 chiffres pour confirmer l'inscription",
        });
    if (confirmCode) {
      confirmControlUiUserTotpEnrollment({
        username,
        totpCode: confirmCode,
        verifyTotp: verifyTotpCode,
      });
      prompter.note("MFA activée pour ce compte.", "Control UI");
    } else if (!options.nonInteractive) {
      prompter.note(
        "Compte créé. Exécutez à nouveau doctor avec confirmation MFA pour activer TOTP.",
        "Control UI",
      );
    }
  }
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
