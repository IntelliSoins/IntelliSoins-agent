/**
 * rag_search built-in tool (Intellisoins fork).
 *
 * Searches the locally indexed document base (pgvector RAG) through the Gateway
 * `rag.search` / `rag.sources` methods. The Gateway owns the sidecar URL and
 * keychain API key; this tool never touches them directly.
 */
import { Type } from "typebox";
import { formatErrorMessage } from "../../infra/errors.js";
import { optionalStringEnum } from "../schema/typebox.js";
import {
  type AnyAgentTool,
  jsonResult,
  readPositiveIntegerParam,
  readStringParam,
} from "./common.js";
import { callGatewayTool, type GatewayCallOptions } from "./gateway.js";

const RAG_ACTIONS = ["search", "sources"] as const;
const RAG_TOP_K_MAX = 20;

const RagToolSchema = Type.Object({
  action: optionalStringEnum(RAG_ACTIONS, {
    description: '"search" (default): semantic search; "sources": list indexed documents',
    default: "search",
  }),
  query: Type.Optional(Type.String({ description: "Search query (required for search)" })),
  topK: Type.Optional(
    Type.Integer({ minimum: 1, maximum: RAG_TOP_K_MAX, description: "Max results (default 5)" }),
  ),
});

type RagToolDeps = {
  callGatewayTool?: typeof callGatewayTool;
};

export function createRagTool(deps?: RagToolDeps): AnyAgentTool {
  const callGateway = deps?.callGatewayTool ?? callGatewayTool;
  // Gateway timeout must outlive the sidecar's own 30s request timeout.
  const gatewayOpts: GatewayCallOptions = { timeoutMs: 60_000 };
  return {
    label: "RAG",
    name: "rag_search",
    description: `Search locally indexed documents (local pgvector RAG knowledge base).

ACTIONS:
- search (default): semantic search; needs query, optional topK (max ${RAG_TOP_K_MAX}). Returns results with score, source (document name), snippet, pages.
- sources: list indexed documents with chunk counts; no other params.

Use search to ground answers in the indexed documents; cite the source and pages.`,
    parameters: RagToolSchema,
    execute: async (_toolCallId, args) => {
      const params = (args ?? {}) as Record<string, unknown>;
      const action = readStringParam(params, "action") ?? "search";
      if (action === "sources") {
        return jsonResult(await callRag(callGateway, "rag.sources", gatewayOpts, {}));
      }
      if (action !== "search") {
        throw new Error(`Unknown action: ${action}`);
      }
      const query = readStringParam(params, "query", { required: true });
      const topK = readPositiveIntegerParam(params, "topK");
      return jsonResult(
        await callRag(callGateway, "rag.search", gatewayOpts, {
          query,
          ...(topK !== undefined ? { topK: Math.min(topK, RAG_TOP_K_MAX) } : {}),
        }),
      );
    },
  };
}

async function callRag(
  callGateway: typeof callGatewayTool,
  method: "rag.search" | "rag.sources",
  gatewayOpts: GatewayCallOptions,
  params: Record<string, unknown>,
) {
  try {
    return await callGateway(method, gatewayOpts, params);
  } catch (error) {
    throw new Error(
      `${method} failed: ${formatErrorMessage(error)} (gateway or RAG sidecar may be unavailable)`,
      { cause: error },
    );
  }
}
