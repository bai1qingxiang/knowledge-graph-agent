import { afterEach, describe, expect, it, vi } from "vitest";
import entry, { createKnowledgeGraphClient } from "./index.js";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";

afterEach(() => vi.restoreAllMocks());

describe("knowledge-graph-tools", () => {
  it("declares the five read-only tools", () => {
    expect(getToolPluginMetadata(entry)?.tools.map((tool) => tool.name)).toEqual([
      "kg_ask", "kg_search", "kg_neighbors", "kg_find_paths", "kg_stats",
    ]);
  });

  it("sends grounded questions to the configured API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ answer: "有证据的回答", citations: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await createKnowledgeGraphClient({ baseUrl: "http://localhost:8123" })
      .ask("使用了什么技术？");
    expect(result).toEqual({ answer: "有证据的回答", citations: [] });
    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("http://localhost:8123/questions/ask");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBe(JSON.stringify({ question: "使用了什么技术？" }));
  });

  it("encodes entity search input", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    await createKnowledgeGraphClient().search("DeepSeek API");
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://127.0.0.1:8000/entities/search?q=DeepSeek%20API",
    );
  });

  it("returns a useful API error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Entity not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(createKnowledgeGraphClient().neighbors("missing"))
      .rejects.toThrow("Knowledge Graph API error: Entity not found");
  });
});
