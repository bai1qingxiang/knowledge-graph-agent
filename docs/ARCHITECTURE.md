# 架构说明

## 设计原则

- **可追溯**：关系可以关联一条或多条原文证据。
- **模型可替换**：业务层不依赖 DeepSeek SDK。
- **存储可替换**：应用层只依赖 `GraphRepository`。
- **写入受控**：当前只允许白名单实体和关系；未来模型抽取先进入候选区。
- **查询受限**：最大路径深度限制为 5，避免无界图遍历。
- **候选隔离**：LLM 输出先进入 `candidate_facts`，审核后才进入正式关系表。

## 分层

```text
Web workbench / API / OpenClaw tools / background jobs
                 ↓
          Application services
                 ↓
        GraphRepository port
                 ↓
 SQLite adapter（现在）/ Neo4j adapter（以后）
```

## 导入与审核

```text
Markdown/TXT
    ↓ chunk_text
DeepSeekFactExtractor
    ↓ 严格 JSON + 本地证据校验
candidate_facts (pending)
    ↓ 人工 accept / reject
entities + relations + evidence
```

`web/` 是无构建步骤的本地工作台，通过同源 FastAPI 调用 `/documents/ingest`、
`/candidates`、`/stats` 和 `/graph`。它不直接访问 SQLite，也不会绕过应用层的
候选审核边界。

## 证据约束问答

```text
用户问题
    ↓
GraphQuestionService 读取带 Evidence 的正式关系（最多 100 条）
    ↓
DeepSeekGraphAnswerer 生成回答和引用 ID
    ↓
本地校验 relation_id / evidence_id
    ↓
回答 + 结构化引用，或“证据不足”
```

候选事实、已拒绝事实和没有证据的手工关系不会进入问答上下文。图谱内容被视为
不可信数据，提示词明确禁止执行其中的指令，以降低文档提示注入风险。

## 尚未实现

- 实体消歧
- PDF/网页解析
- 向量检索
- Neo4j 适配器
- OpenClaw 候选写入工具或 MCP 服务
- 鉴权、限流、审计日志
