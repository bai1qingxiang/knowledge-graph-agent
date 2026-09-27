# 文档抽取与审核流程

## 安全边界

- DeepSeek 只能生成候选事实；
- 证据引用必须逐字存在于原文块中；
- 实体类型和关系类型必须在白名单中；
- 人工调用 `accept` 后，事实才会进入正式图谱；
- 已接受或拒绝的候选不能重复审核。

## 1. 配置 API Key

```powershell
$env:DEEPSEEK_API_KEY="你的 API Key"
$env:DEEPSEEK_MODEL="deepseek-flash"
```

Key 只进入当前终端进程，不应提交到 Git。

## 2. 导入文件

命令行方式：

```powershell
python scripts\ingest_file.py .\design.md
```

HTTP 方式：

```json
POST /documents/ingest
{
  "document_id": "design.md",
  "source_uri": "design.md",
  "text": "知识图谱 Agent 使用 DeepSeek 抽取实体关系。"
}
```

## 3. 查看候选事实

```text
GET /candidates?status=pending
```

重点检查：

- 实体类型是否合理；
- 关系方向是否正确；
- `evidence_quote` 是否能支持该结论；
- 置信度是否与证据强度一致。

## 4. 审核

```text
POST /candidates/{candidate_id}/accept
POST /candidates/{candidate_id}/reject
```

接受后会自动：

1. 按实体类型和标准名称复用或创建实体；
2. 创建正式关系；
3. 将原文引用关联为 Evidence；
4. 把候选状态改为 `accepted`。

## 当前限制

- 只支持 Markdown/TXT 文本；
- 实体消歧仅使用“类型 + 名称”精确匹配；
- 暂无可视化审核页面；
- 同一事实由不同文档证明时，暂时会形成多条关系；
- DeepSeek 网络故障时没有后台重试队列。

