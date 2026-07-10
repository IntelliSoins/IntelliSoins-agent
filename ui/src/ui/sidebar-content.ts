// Control UI module implements sidebar content behavior.
export type SidebarFullMessageRequest = {
  sessionKey: string;
  agentId?: string;
  messageId: string;
  kind: "assistant_message" | "tool_output";
};

export type SidebarContentBase = {
  rawText?: string | null;
  fullMessageRequest?: SidebarFullMessageRequest;
  unavailableReason?: "not_found" | "oversized" | "not_visible" | null;
};

export type MarkdownSidebarContent = SidebarContentBase & {
  kind: "markdown";
  content: string;
};

export type CanvasSidebarContent = SidebarContentBase & {
  kind: "canvas";
  docId: string;
  title?: string;
  entryUrl: string;
  preferredHeight?: number;
};

export type AgentFileSidebarContent = SidebarContentBase & {
  kind: "agentFile";
  fileName: string;
  agentId: string;
  missing?: boolean;
};

export type SidebarContent =
  | MarkdownSidebarContent
  | CanvasSidebarContent
  | AgentFileSidebarContent;

export function resolveSidebarRawText(
  content: SidebarContent | null | undefined,
): string | null | undefined {
  if (!content) {
    return null;
  }
  return content.rawText;
}
