type PluginConfig = {
    baseUrl?: string;
    timeoutMs?: number;
};
export declare function createKnowledgeGraphClient(config?: PluginConfig, signal?: AbortSignal): {
    stats: () => Promise<any>;
    ask: (question: string) => Promise<any>;
    search: (query: string) => Promise<any>;
    neighbors: (entityId: string, predicate?: string) => Promise<any>;
    findPaths: (sourceId: string, targetId: string, maxDepth: number) => Promise<any>;
};
declare const _default: import("openclaw/plugin-sdk/tool-plugin").DefinedToolPluginEntry;
export default _default;
