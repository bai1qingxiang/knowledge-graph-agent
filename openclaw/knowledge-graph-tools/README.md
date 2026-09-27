# Knowledge Graph Tools for OpenClaw

本地 OpenClaw Tool Plugin，通过 HTTP 调用知识图谱 Agent。插件只提供只读查询，不会创建候选事实或修改正式图谱。

## 工具

| 工具 | 用途 |
|---|---|
| `kg_ask` | 使用已审核事实和证据回答自然语言问题 |
| `kg_search` | 按名称或别名搜索实体 |
| `kg_neighbors` | 查询指定实体的相邻关系 |
| `kg_find_paths` | 查询两个实体间最多 1～5 跳路径 |
| `kg_stats` | 获取实体、关系、证据和审核统计 |

## 配置

- `baseUrl`：知识图谱 API 地址，默认 `http://127.0.0.1:8000`；
- `timeoutMs`：请求超时，默认 30000 毫秒。

OpenClaw 在 WSL 中运行，因此知识图谱 API 也应在同一 WSL 中启动。详见项目根目录 README。

## 开发验证

```bash
npm install
npm run plugin:validate
npm test
```
