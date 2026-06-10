// Gateway Protocol schema module defines protocol validation shapes.
import { Type } from "typebox";
import { NonEmptyString } from "./primitives.js";

/**
 * Local RAG pipeline schemas (Intellisoins fork).
 *
 * These contracts back the Control UI document ingestion and semantic search
 * over the local pgvector sidecar. Everything stays on-device (Loi 25).
 */

/** Uploads one base64-encoded document for RAG ingestion. ~6 MB binary max. */
export const RagIngestParamsSchema = Type.Object(
  {
    fileName: NonEmptyString,
    dataBase64: Type.String({ minLength: 1, maxLength: 8_000_000 }),
  },
  { additionalProperties: false },
);

/** Acknowledges an accepted ingestion job. */
export const RagIngestResultSchema = Type.Object(
  {
    jobId: NonEmptyString,
  },
  { additionalProperties: false },
);

/** Lists recent ingestion jobs. */
export const RagJobsParamsSchema = Type.Object({}, { additionalProperties: false });

/** One ingestion job record, newest first in list results. */
export const RagJobSchema = Type.Object(
  {
    id: NonEmptyString,
    fileName: NonEmptyString,
    status: Type.Union([Type.Literal("running"), Type.Literal("done"), Type.Literal("error")]),
    chunks: Type.Optional(Type.Integer({ minimum: 0 })),
    error: Type.Optional(Type.String()),
    startedAt: Type.Number(),
    finishedAt: Type.Optional(Type.Number()),
  },
  { additionalProperties: false },
);

export const RagJobsResultSchema = Type.Object(
  {
    jobs: Type.Array(RagJobSchema),
  },
  { additionalProperties: false },
);

/** Semantic search over the ingested documents. */
export const RagSearchParamsSchema = Type.Object(
  {
    query: NonEmptyString,
    topK: Type.Optional(Type.Integer({ minimum: 1, maximum: 20 })),
  },
  { additionalProperties: false },
);

export const RagSearchResultSchema = Type.Object(
  {
    results: Type.Array(
      Type.Object(
        {
          score: Type.Number(),
          source: Type.String(),
          snippet: Type.String(),
          pages: Type.Array(Type.Number()),
        },
        { additionalProperties: false },
      ),
    ),
  },
  { additionalProperties: false },
);

/** Lists ingested document sources with chunk counts. */
export const RagSourcesParamsSchema = Type.Object({}, { additionalProperties: false });

export const RagSourcesResultSchema = Type.Object(
  {
    sources: Type.Array(
      Type.Object(
        {
          source: Type.String(),
          chunks: Type.Integer({ minimum: 0 }),
          lastIngested: Type.Optional(Type.String()),
        },
        { additionalProperties: false },
      ),
    ),
  },
  { additionalProperties: false },
);
