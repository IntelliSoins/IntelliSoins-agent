// rag_search tool tests: schema shape, RPC param mapping, and gateway failure wrapping.
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { callGatewayTool } from "./gateway.js";
import { createRagTool } from "./rag-tool.js";

const callGatewayMock = vi.fn();

function createTestRagTool() {
  return createRagTool({
    callGatewayTool: (async (method, _gatewayOpts, params) =>
      await callGatewayMock(method, params)) as typeof callGatewayTool,
  });
}

describe("rag tool", () => {
  beforeEach(() => {
    callGatewayMock.mockReset();
  });

  it("exposes a flat string enum action schema", () => {
    const tool = createTestRagTool();
    const schema = tool.parameters as {
      properties?: Record<string, { enum?: string[]; anyOf?: unknown }>;
    };
    expect(tool.name).toBe("rag_search");
    expect(schema.properties?.action?.enum).toEqual(["search", "sources"]);
    expect(schema.properties?.action?.anyOf).toBeUndefined();
  });

  it("defaults to search and maps query/topK to rag.search", async () => {
    callGatewayMock.mockResolvedValue({ results: [] });
    const tool = createTestRagTool();
    await tool.execute("call-1", { query: "metoprolol", topK: 3 });
    expect(callGatewayMock).toHaveBeenCalledTimes(1);
    expect(callGatewayMock).toHaveBeenCalledWith("rag.search", { query: "metoprolol", topK: 3 });
  });

  it("requires query for search", async () => {
    const tool = createTestRagTool();
    await expect(tool.execute("call-1", {})).rejects.toThrow(/query/);
    expect(callGatewayMock).not.toHaveBeenCalled();
  });

  it("maps sources action to rag.sources", async () => {
    callGatewayMock.mockResolvedValue({ sources: [] });
    const tool = createTestRagTool();
    await tool.execute("call-1", { action: "sources" });
    expect(callGatewayMock).toHaveBeenCalledWith("rag.sources", {});
  });

  it("wraps gateway failures with an availability hint", async () => {
    callGatewayMock.mockRejectedValue(new Error("connect ECONNREFUSED"));
    const tool = createTestRagTool();
    await expect(tool.execute("call-1", { query: "metoprolol" })).rejects.toThrow(
      /rag\.search failed: .*ECONNREFUSED.*(gateway or RAG sidecar may be unavailable)/,
    );
  });
});
