import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

type PluginConfig = {
  baseUrl?: string;
  timeoutMs?: number;
};

export function createKnowledgeGraphClient(config: PluginConfig = {}, signal?: AbortSignal) {
  const baseUrl = (config.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");
  const timeoutMs = Math.min(Math.max(config.timeoutMs || 30_000, 1_000), 120_000);

  async function request(path: string, init: RequestInit = {}) {
    const url = new URL(path, `${baseUrl}/`);
    if (!/^https?:$/.test(url.protocol)) {
      throw new Error("Knowledge Graph baseUrl must use http or https");
    }
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    const requestSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
    let response: Response;
    try {
      response = await fetch(url, {
        ...init,
        signal: requestSignal,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(init.headers || {}),
        },
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `Cannot reach Knowledge Graph API at ${baseUrl}. Start the API in WSL first. (${message})`,
      );
    }
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${response.status}`;
      throw new Error(`Knowledge Graph API error: ${detail}`);
    }
    return body;
  }

  return {
    stats: () => request("stats"),
    ask: (question: string) => request("questions/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
    search: (query: string) => request(`entities/search?q=${encodeURIComponent(query)}`),
    neighbors: (entityId: string, predicate?: string) => {
      const suffix = predicate ? `?predicate=${encodeURIComponent(predicate)}` : "";
      return request(`entities/${encodeURIComponent(entityId)}/neighbors${suffix}`);
    },
    findPaths: (sourceId: string, targetId: string, maxDepth: number) => request(
      `paths?source_id=${encodeURIComponent(sourceId)}&target_id=${encodeURIComponent(targetId)}&max_depth=${maxDepth}`,
    ),
  };
}

const configSchema = Type.Object(
  {
    baseUrl: Type.Optional(Type.String({
      description: "Knowledge Graph Agent API URL.",
      default: DEFAULT_BASE_URL,
    })),
    timeoutMs: Type.Optional(Type.Integer({
      description: "HTTP request timeout in milliseconds.",
      minimum: 1000,
      maximum: 120000,
      default: 30000,
    })),
  },
  { additionalProperties: false },
);

export default defineToolPlugin({
  id: "knowledge-graph-tools",
  name: "Knowledge Graph Tools",
  description: "Query a local, human-reviewed knowledge graph with traceable evidence.",
  configSchema,
  tools: (tool) => [
    tool({
      name: "kg_ask",
      label: "Ask Knowledge Graph",
      description: "Answer a natural-language question using only accepted graph facts and their evidence. Prefer this for evidence-backed questions.",
      parameters: Type.Object({
        question: Type.String({ description: "Question to answer from the knowledge graph.", minLength: 1, maxLength: 1000 }),
      }),
      async execute({ question }, config, context) {
        return createKnowledgeGraphClient(config, context.signal).ask(question);
      },
    }),
    tool({
      name: "kg_search",
      label: "Search Knowledge Graph",
      description: "Search accepted graph entities by name or alias. Use returned entity IDs with neighbor and path tools.",
      parameters: Type.Object({
        query: Type.String({ description: "Entity name or alias to search for.", minLength: 1, maxLength: 200 }),
      }),
      async execute({ query }, config, context) {
        return createKnowledgeGraphClient(config, context.signal).search(query);
      },
    }),
    tool({
      name: "kg_neighbors",
      label: "Knowledge Graph Neighbors",
      description: "List accepted relations connected to one entity ID, optionally filtered by predicate.",
      parameters: Type.Object({
        entityId: Type.String({ description: "Entity ID returned by kg_search.", minLength: 1 }),
        predicate: Type.Optional(Type.String({ description: "Optional predicate such as USES or DEPENDS_ON." })),
      }),
      async execute({ entityId, predicate }, config, context) {
        return createKnowledgeGraphClient(config, context.signal).neighbors(entityId, predicate);
      },
    }),
    tool({
      name: "kg_find_paths",
      label: "Find Knowledge Graph Paths",
      description: "Find accepted relation paths between two entity IDs. Search entities first when IDs are unknown.",
      parameters: Type.Object({
        sourceId: Type.String({ description: "Starting entity ID.", minLength: 1 }),
        targetId: Type.String({ description: "Destination entity ID.", minLength: 1 }),
        maxDepth: Type.Optional(Type.Integer({ description: "Maximum path depth from 1 to 5.", minimum: 1, maximum: 5, default: 3 })),
      }),
      async execute({ sourceId, targetId, maxDepth = 3 }, config, context) {
        return createKnowledgeGraphClient(config, context.signal).findPaths(sourceId, targetId, maxDepth);
      },
    }),
    tool({
      name: "kg_stats",
      label: "Knowledge Graph Stats",
      description: "Return entity, relation, evidence, and candidate-review counts for the local knowledge graph.",
      parameters: Type.Object({}),
      async execute(_params, config, context) {
        return createKnowledgeGraphClient(config, context.signal).stats();
      },
    }),
  ],
});
