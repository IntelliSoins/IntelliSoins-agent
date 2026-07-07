// Control UI tests cover navigation behavior.
import { describe, expect, it } from "vitest";
import {
  TAB_GROUPS,
  SETTINGS_TABS,
  iconForTab,
  inferBasePathFromPathname,
  isSettingsTab,
  isTabVisibleForProfile,
  normalizeBasePath,
  normalizePath,
  pathForTab,
  resolveTabForProfile,
  settingsTabsForProfile,
  subtitleForTab,
  tabFromPath,
  tabGroupsForProfile,
  titleForTab,
  type Tab,
} from "./navigation.ts";

/** All valid tab identifiers derived from visible groups plus routed settings slices. */
const ALL_TABS: Tab[] = Array.from(
  new Set<Tab>([...(TAB_GROUPS.flatMap((group) => group.tabs) as Tab[]), ...SETTINGS_TABS]),
);

const leadingSlashNormalizerCases = [
  { name: "normalizeBasePath", normalize: normalizeBasePath, input: "ui", expected: "/ui" },
  { name: "normalizePath", normalize: normalizePath, input: "chat", expected: "/chat" },
];

describe("iconForTab", () => {
  it("returns stable icons for every tab", () => {
    expect(Object.fromEntries(ALL_TABS.map((tab) => [tab, iconForTab(tab)]))).toEqual({
      chat: "messageSquare",
      overview: "barChart",
      activity: "activity",
      workboard: "folder",
      channels: "link",
      instances: "radio",
      sessions: "fileText",
      usage: "barChart",
      cron: "loader",
      agents: "folder",
      skills: "zap",
      skillWorkshop: "wrench",
      nodes: "monitor",
      dreams: "moon",
      rag: "book",
      config: "settings",
      communications: "send",
      appearance: "spark",
      automation: "terminal",
      mcp: "wrench",
      infrastructure: "globe",
      aiAgents: "brain",
      debug: "bug",
      logs: "scrollText",
    });
  });

  it("returns a fallback icon for unknown tab", () => {
    // TypeScript won't allow this normally, but runtime could receive unexpected values
    const unknownTab = "unknown" as Tab;
    expect(iconForTab(unknownTab)).toBe("folder");
  });
});

describe("titleForTab", () => {
  it("returns expected titles for every tab", () => {
    expect(Object.fromEntries(ALL_TABS.map((tab) => [tab, titleForTab(tab)]))).toEqual({
      chat: "Assistant",
      overview: "Home",
      activity: "Recent Activity",
      workboard: "Active Tasks",
      channels: "Messages",
      instances: "Connected Stations",
      sessions: "Conversations",
      usage: "Usage & Costs",
      cron: "Schedules",
      agents: "Assistants",
      skills: "Competencies",
      skillWorkshop: "Competency Workshop",
      nodes: "Connected Devices",
      dreams: "Background Memory",
      rag: "Document Search",
      config: "Settings",
      communications: "Messages & Voice",
      appearance: "Appearance",
      automation: "Automations",
      mcp: "Third-Party Services",
      infrastructure: "Server & Network",
      aiAgents: "AI & Assistants",
      debug: "Diagnostics",
      logs: "System Log",
    });
  });
});

describe("subtitleForTab", () => {
  it("returns expected subtitles for every tab", () => {
    expect(Object.fromEntries(ALL_TABS.map((tab) => [tab, subtitleForTab(tab)]))).toEqual({
      chat: "Talk to the pharmacy assistant for quick help.",
      overview: "Service status, connection, and alerts.",
      activity: "What the assistant did recently in this browser.",
      workboard: "Tasks in progress, reminders, and handoffs.",
      channels: "Messaging channels and settings.",
      instances: "Active connections from computers and tablets.",
      sessions: "Active conversations and defaults.",
      usage: "AI usage and costs.",
      cron: "Recurring reminders and automations.",
      agents: "Assistant profiles, tools, and identities.",
      skills: "Competencies and API keys.",
      skillWorkshop: "Review and apply competency proposals before they go live.",
      nodes: "Paired devices and commands.",
      dreams: "Background memory consolidation and reflection.",
      rag: "Document ingestion, indexing, and search.",
      config: "General IntelliSoins configuration.",
      communications: "Channels, messages, and audio settings.",
      appearance: "Theme, UI, and setup wizard settings.",
      automation: "Commands, hooks, schedules, and plugins.",
      mcp: "Third-party service connections, auth, tools, and diagnostics.",
      infrastructure: "IntelliSoins Connector, web, browser, and media settings.",
      aiAgents: "Assistants, models, competencies, tools, memory, and conversations.",
      debug: "Snapshots, events, and technical diagnostics.",
      logs: "Live IntelliSoins Connector logs.",
    });
  });
});

describe("leading slash path normalizers", () => {
  it.each(leadingSlashNormalizerCases)(
    "$name adds leading slash if missing",
    ({ expected, input, normalize }) => {
      expect(normalize(input)).toBe(expected);
    },
  );
});

describe("normalizeBasePath", () => {
  it("returns empty string for falsy input", () => {
    expect(normalizeBasePath("")).toBe("");
  });

  it("removes trailing slash", () => {
    expect(normalizeBasePath("/ui/")).toBe("/ui");
  });

  it("returns empty string for root path", () => {
    expect(normalizeBasePath("/")).toBe("");
  });

  it("handles nested paths", () => {
    expect(normalizeBasePath("/apps/openclaw")).toBe("/apps/openclaw");
  });
});

describe("normalizePath", () => {
  it("returns / for falsy input", () => {
    expect(normalizePath("")).toBe("/");
  });

  it("removes trailing slash except for root", () => {
    expect(normalizePath("/chat/")).toBe("/chat");
    expect(normalizePath("/")).toBe("/");
  });
});

describe("pathForTab", () => {
  it("returns correct path without base", () => {
    expect(pathForTab("chat")).toBe("/chat");
    expect(pathForTab("overview")).toBe("/overview");
  });

  it("prepends base path", () => {
    expect(pathForTab("chat", "/ui")).toBe("/ui/chat");
    expect(pathForTab("sessions", "/apps/openclaw")).toBe("/apps/openclaw/sessions");
  });
});

describe("tabFromPath", () => {
  it("returns tab for valid path", () => {
    expect(tabFromPath("/chat")).toBe("chat");
    expect(tabFromPath("/overview")).toBe("overview");
    expect(tabFromPath("/activity")).toBe("activity");
    expect(tabFromPath("/sessions")).toBe("sessions");
    expect(tabFromPath("/dreaming")).toBe("dreams");
    expect(tabFromPath("/dreams")).toBe("dreams");
  });

  it("returns chat for root path", () => {
    expect(tabFromPath("/")).toBe("chat");
  });

  it("handles base paths", () => {
    expect(tabFromPath("/ui/chat", "/ui")).toBe("chat");
    expect(tabFromPath("/apps/openclaw/sessions", "/apps/openclaw")).toBe("sessions");
  });

  it("returns null for unknown path", () => {
    expect(tabFromPath("/unknown")).toBeNull();
  });

  it("is case-insensitive", () => {
    expect(tabFromPath("/CHAT")).toBe("chat");
    expect(tabFromPath("/Overview")).toBe("overview");
  });
});

describe("inferBasePathFromPathname", () => {
  it("returns empty string for root", () => {
    expect(inferBasePathFromPathname("/")).toBe("");
  });

  it("returns empty string for direct tab path", () => {
    expect(inferBasePathFromPathname("/chat")).toBe("");
    expect(inferBasePathFromPathname("/overview")).toBe("");
    expect(inferBasePathFromPathname("/dreaming")).toBe("");
    expect(inferBasePathFromPathname("/dreams")).toBe("");
  });

  it("infers base path from nested paths", () => {
    expect(inferBasePathFromPathname("/ui/chat")).toBe("/ui");
    expect(inferBasePathFromPathname("/apps/openclaw/sessions")).toBe("/apps/openclaw");
  });

  it("handles index.html suffix", () => {
    expect(inferBasePathFromPathname("/index.html")).toBe("");
    expect(inferBasePathFromPathname("/ui/index.html")).toBe("/ui");
  });
});

describe("TAB_GROUPS", () => {
  it("contains all expected groups", () => {
    expect(TAB_GROUPS.map((g) => g.label)).toEqual(["chat", "control", "agent", "settings"]);
  });

  it("all tabs are unique", () => {
    const allTabs = TAB_GROUPS.flatMap((g) => g.tabs);
    const uniqueTabs = new Set(allTabs);
    expect(uniqueTabs.size).toBe(allTabs.length);
  });

  it("keeps detailed settings slices routed but out of the root sidebar", () => {
    const settings = TAB_GROUPS.find((group) => group.label === "settings");
    expect(settings?.tabs).toEqual(["config"]);
    expect(SETTINGS_TABS).toEqual([
      "config",
      "channels",
      "communications",
      "appearance",
      "automation",
      "mcp",
      "infrastructure",
      "aiAgents",
      "debug",
      "logs",
    ]);
    expect(SETTINGS_TABS.every((tab) => isSettingsTab(tab))).toBe(true);
  });
});

describe("interface profile navigation", () => {
  it("hides advanced tabs in pharmacy mode", () => {
    expect(isTabVisibleForProfile("debug", "pharmacy")).toBe(false);
    expect(isTabVisibleForProfile("mcp", "pharmacy")).toBe(false);
    expect(isTabVisibleForProfile("overview", "pharmacy")).toBe(true);
    expect(isTabVisibleForProfile("rag", "pharmacy")).toBe(true);
    expect(isTabVisibleForProfile("appearance", "pharmacy")).toBe(true);
    expect(isTabVisibleForProfile("config", "pharmacy")).toBe(false);
  });

  it("shows all tabs in admin mode", () => {
    expect(isTabVisibleForProfile("debug", "admin")).toBe(true);
    expect(isTabVisibleForProfile("config", "admin")).toBe(true);
  });

  it("filters sidebar groups for pharmacy mode", () => {
    const groups = tabGroupsForProfile("pharmacy");
    const tabs = groups.flatMap((group) => group.tabs);
    expect(tabs).toContain("chat");
    expect(tabs).toContain("overview");
    expect(tabs).not.toContain("debug");
    expect(tabs).not.toContain("agents");
  });

  it("redirects hidden settings tabs to appearance", () => {
    expect(resolveTabForProfile("debug", "pharmacy")).toBe("appearance");
    expect(resolveTabForProfile("overview", "pharmacy")).toBe("overview");
  });

  it("limits pharmacy settings navigation", () => {
    expect(settingsTabsForProfile("pharmacy")).toEqual([
      "channels",
      "communications",
      "appearance",
    ]);
    expect(settingsTabsForProfile("admin").length).toBe(SETTINGS_TABS.length);
  });
});
