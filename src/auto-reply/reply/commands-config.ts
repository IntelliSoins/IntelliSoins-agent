import { resolveChannelConfigWrites } from "../../channels/plugins/config-writes.js";
import { normalizeChannelId } from "../../channels/registry.js";
import {
  getConfigValueAtPath,
  parseConfigPath,
  setConfigValueAtPath,
  unsetConfigValueAtPath,
} from "../../config/config-paths.js";
import {
  readConfigFileSnapshot,
  validateConfigObjectWithPlugins,
  writeConfigFile,
} from "../../config/config.js";
import {
  getConfigOverrides,
  resetConfigOverrides,
  setConfigOverride,
  unsetConfigOverride,
} from "../../config/runtime-overrides.js";
import {
  rejectUnauthorizedCommand,
  requireCommandFlagEnabled,
  requireGatewayClientScopeForInternalChannel,
} from "./command-gates.js";
import type { CommandHandler } from "./commands-types.js";
import { parseConfigCommand } from "./config-commands.js";
import { parseDebugCommand } from "./debug-commands.js";

export const handleConfigCommand: CommandHandler = async (params, allowTextCommands) => {
  if (!allowTextCommands) {
    return null;
  }
  const configCommand = parseConfigCommand(params.command.commandBodyNormalized);
  if (!configCommand) {
    return null;
  }
  const unauthorized = rejectUnauthorizedCommand(params, "/config");
  if (unauthorized) {
    return unauthorized;
  }
  const disabled = requireCommandFlagEnabled(params.cfg, {
    label: "/config",
    configKey: "config",
  });
  if (disabled) {
    return disabled;
  }
  if (configCommand.action === "error") {
    return {
      shouldContinue: false,
      reply: { text: `⚠️ ${configCommand.message}` },
    };
  }

  if (configCommand.action === "set" || configCommand.action === "unset") {
    const missingAdminScope = requireGatewayClientScopeForInternalChannel(params, {
      label: "/config write",
      allowedScopes: ["operator.admin"],
      missingText: "❌ /config set|unset requires operator.admin for gateway clients.",
    });
    if (missingAdminScope) {
      return missingAdminScope;
    }
    const channelId = params.command.channelId ?? normalizeChannelId(params.command.channel);
    const allowWrites = resolveChannelConfigWrites({
      cfg: params.cfg,
      channelId,
      accountId: params.ctx.AccountId,
    });
    if (!allowWrites) {
      const channelLabel = channelId ?? "this channel";
      const hint = channelId
        ? `channels.${channelId}.configWrites=true`
        : "channels.<channel>.configWrites=true";
      return {
        shouldContinue: false,
        reply: {
          text: `⚠️ L'écriture de config est désactivée pour ${channelLabel}. Définir ${hint} pour activer.`,
        },
      };
    }
  }

  const snapshot = await readConfigFileSnapshot();
  if (!snapshot.valid || !snapshot.parsed || typeof snapshot.parsed !== "object") {
    return {
      shouldContinue: false,
      reply: {
        text: "⚠️ Le fichier de config est invalide; corrigez-le avant d'utiliser /config.",
      },
    };
  }
  const parsedBase = structuredClone(snapshot.parsed as Record<string, unknown>);

  if (configCommand.action === "show") {
    const pathRaw = configCommand.path?.trim();
    if (pathRaw) {
      const parsedPath = parseConfigPath(pathRaw);
      if (!parsedPath.ok || !parsedPath.path) {
        return {
          shouldContinue: false,
          reply: { text: `⚠️ ${parsedPath.error ?? "Invalid path."}` },
        };
      }
      const value = getConfigValueAtPath(parsedBase, parsedPath.path);
      const rendered = JSON.stringify(value ?? null, null, 2);
      return {
        shouldContinue: false,
        reply: {
          text: `⚙️ Config ${pathRaw} :\n\`\`\`json\n${rendered}\n\`\`\``,
        },
      };
    }
    const json = JSON.stringify(parsedBase, null, 2);
    return {
      shouldContinue: false,
      reply: { text: `⚙️ Config (brut) :\n\`\`\`json\n${json}\n\`\`\`` },
    };
  }

  if (configCommand.action === "unset") {
    const parsedPath = parseConfigPath(configCommand.path);
    if (!parsedPath.ok || !parsedPath.path) {
      return {
        shouldContinue: false,
        reply: { text: `⚠️ ${parsedPath.error ?? "Invalid path."}` },
      };
    }
    const removed = unsetConfigValueAtPath(parsedBase, parsedPath.path);
    if (!removed) {
      return {
        shouldContinue: false,
        reply: { text: `⚙️ Aucune valeur de config trouvée pour ${configCommand.path}.` },
      };
    }
    const validated = validateConfigObjectWithPlugins(parsedBase);
    if (!validated.ok) {
      const issue = validated.issues[0];
      return {
        shouldContinue: false,
        reply: {
          text: `⚠️ Config invalide après suppression (${issue.path}: ${issue.message}).`,
        },
      };
    }
    await writeConfigFile(validated.config);
    return {
      shouldContinue: false,
      reply: { text: `⚙️ Config mise à jour : ${configCommand.path} supprimé.` },
    };
  }

  if (configCommand.action === "set") {
    const parsedPath = parseConfigPath(configCommand.path);
    if (!parsedPath.ok || !parsedPath.path) {
      return {
        shouldContinue: false,
        reply: { text: `⚠️ ${parsedPath.error ?? "Invalid path."}` },
      };
    }
    setConfigValueAtPath(parsedBase, parsedPath.path, configCommand.value);
    const validated = validateConfigObjectWithPlugins(parsedBase);
    if (!validated.ok) {
      const issue = validated.issues[0];
      return {
        shouldContinue: false,
        reply: {
          text: `⚠️ Config invalide après modification (${issue.path}: ${issue.message}).`,
        },
      };
    }
    await writeConfigFile(validated.config);
    const valueLabel =
      typeof configCommand.value === "string"
        ? `"${configCommand.value}"`
        : JSON.stringify(configCommand.value);
    return {
      shouldContinue: false,
      reply: {
        text: `⚙️ Config mise à jour : ${configCommand.path}=${valueLabel ?? "null"}`,
      },
    };
  }

  return null;
};

export const handleDebugCommand: CommandHandler = async (params, allowTextCommands) => {
  if (!allowTextCommands) {
    return null;
  }
  const debugCommand = parseDebugCommand(params.command.commandBodyNormalized);
  if (!debugCommand) {
    return null;
  }
  const unauthorized = rejectUnauthorizedCommand(params, "/debug");
  if (unauthorized) {
    return unauthorized;
  }
  const disabled = requireCommandFlagEnabled(params.cfg, {
    label: "/debug",
    configKey: "debug",
  });
  if (disabled) {
    return disabled;
  }
  if (debugCommand.action === "error") {
    return {
      shouldContinue: false,
      reply: { text: `⚠️ ${debugCommand.message}` },
    };
  }
  if (debugCommand.action === "show") {
    const overrides = getConfigOverrides();
    const hasOverrides = Object.keys(overrides).length > 0;
    if (!hasOverrides) {
      return {
        shouldContinue: false,
        reply: { text: "⚙️ Surcharges debug : (aucune)" },
      };
    }
    const json = JSON.stringify(overrides, null, 2);
    return {
      shouldContinue: false,
      reply: {
        text: `⚙️ Surcharges debug (mémoire seule) :\n\`\`\`json\n${json}\n\`\`\``,
      },
    };
  }
  if (debugCommand.action === "reset") {
    resetConfigOverrides();
    return {
      shouldContinue: false,
      reply: { text: "⚙️ Surcharges debug supprimées; utilisation de la config sur disque." },
    };
  }
  if (debugCommand.action === "unset") {
    const result = unsetConfigOverride(debugCommand.path);
    if (!result.ok) {
      return {
        shouldContinue: false,
        reply: { text: `⚠️ ${result.error ?? "Invalid path."}` },
      };
    }
    if (!result.removed) {
      return {
        shouldContinue: false,
        reply: {
          text: `⚙️ Aucune surcharge debug trouvée pour ${debugCommand.path}.`,
        },
      };
    }
    return {
      shouldContinue: false,
      reply: { text: `⚙️ Surcharge debug supprimée pour ${debugCommand.path}.` },
    };
  }
  if (debugCommand.action === "set") {
    const result = setConfigOverride(debugCommand.path, debugCommand.value);
    if (!result.ok) {
      return {
        shouldContinue: false,
        reply: { text: `⚠️ ${result.error ?? "Invalid override."}` },
      };
    }
    const valueLabel =
      typeof debugCommand.value === "string"
        ? `"${debugCommand.value}"`
        : JSON.stringify(debugCommand.value);
    return {
      shouldContinue: false,
      reply: {
        text: `⚙️ Surcharge debug définie : ${debugCommand.path}=${valueLabel ?? "null"}`,
      },
    };
  }

  return null;
};
