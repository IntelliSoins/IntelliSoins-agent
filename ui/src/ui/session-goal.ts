import { t } from "../i18n/index.ts";
// Control UI module implements session goal behavior.
import type { SessionGoal } from "./types.ts";

export function formatGoalTokenCount(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "0";
  }
  if (value < 1000) {
    return String(Math.round(value));
  }
  if (value < 1_000_000) {
    const rounded = value >= 10_000 ? Math.round(value / 1000) : Math.round(value / 100) / 10;
    if (rounded >= 1000) {
      return "1m";
    }
    return `${rounded}k`;
  }
  const rounded =
    value >= 10_000_000 ? Math.round(value / 1_000_000) : Math.round(value / 100_000) / 10;
  return `${rounded}m`;
}

export function formatGoalUsage(goal: SessionGoal): string | null {
  if (typeof goal.tokenBudget === "number" && Number.isFinite(goal.tokenBudget)) {
    return `${formatGoalTokenCount(goal.tokensUsed)}/${formatGoalTokenCount(goal.tokenBudget)}`;
  }
  if (goal.tokensUsed > 0) {
    return t("sessionsView.goalTokensUsed", { count: formatGoalTokenCount(goal.tokensUsed) });
  }
  return null;
}

export function formatGoalStatusLabel(status: SessionGoal["status"]): string {
  switch (status) {
    case "active":
      return t("sessionsView.goalActive");
    case "paused":
      return t("sessionsView.goalPaused");
    case "blocked":
      return t("sessionsView.goalBlocked");
    case "usage_limited":
      return t("sessionsView.goalUsageLimited");
    case "budget_limited":
      return t("sessionsView.goalBudgetLimited");
    case "complete":
      return t("sessionsView.goalComplete");
  }
  const unreachable: never = status;
  return unreachable;
}

export function formatGoalSummary(goal: SessionGoal): string {
  const usage = formatGoalUsage(goal);
  const status = formatGoalStatusLabel(goal.status);
  return usage ? `${status} (${usage})` : status;
}

export function formatGoalDetail(goal: SessionGoal): string {
  const note = goal.lastStatusNote ? ` - ${goal.lastStatusNote}` : "";
  return `${formatGoalSummary(goal)}: ${goal.objective}${note}`;
}
