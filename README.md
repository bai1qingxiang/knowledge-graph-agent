# 知识图谱 Agent

一个本地运行、证据可追溯的知识图谱 Agent。它使用 DeepSeek 从 Markdown/TXT 文档中提出候选事实，由人审核后再写入正式图谱，避免模型生成的错误内容直接污染知识库。

当前版本：`0.5.0`

## 已实现功能

- DeepSeek 抽取实体、关系、证据和置信度；
- 长文自动分块，证据必须逐字存在于原文；
- 候选事实接受/拒绝工作流；
- 接受后自动创建或复用实体，并保存关系与证据；
- 实体搜索、邻居查询、1～5 跳路径查询；
- 网页端导入、审核、统计和图谱可视化；
- 基于正式图谱和原文证据的自然语言问答；
- OpenClaw Tool Plugin，提供五个只读知识图谱工具；
- SQLite 本地持久化和 FastAPI 接口；
- 分层架构，可继续替换 Neo4j、增加向量检索或扩展 OpenClaw 工具。

## 工作流程

```text
Markdown/TXT → 文本分块 → DeepSeek 结构化抽取
             → 白名单与原文证据校验 → 候选事实
             → 人工接受/拒绝 → 实体 + 正式关系 + Evidence
```

模型只负责提出候选，人负责决定事实是否进入图谱。

## 环境要求

- Windows 10/11；
- Python 3.11 或更高版本；
- 可访问 DeepSeek API；
- 一个可用的 DeepSeek API Key。

以下命令默认在项目根目录执行。项目可以放在任意目录，例如：

```text
C:\Users\<你的用户名>\Projects\knowledge-graph-agent
```

## 第一次安装

当前电脑已经创建好 `.venv` 并安装了依赖。如果换电脑或删除虚拟环境，在 PowerShell 中执行：

```powershell
cd "$HOME\OneDrive\Desktop\知识图谱agent"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

这里直接调用虚拟环境中的 Python，不依赖 PowerShell 的脚本执行策略，因此不必执行 `Activate.ps1`。

## 配置 DeepSeek API Key

### 方法一：仅对当前 PowerShell 窗口生效

```powershell
$env:DEEPSEEK_API_KEY="sk-你的新密钥"
$env:DEEPSEEK_MODEL="deepseek-flash"
```

关闭该 PowerShell 窗口后，环境变量会消失。检查是否配置成功，但不显示密钥内容：

```powershell
if ($env:DEEPSEEK_API_KEY) {
    "API Key 已配置，长度：$($env:DEEPSEEK_API_KEY.Length)"
} else {
    "API Key 尚未配置"
}
```

### 方法二：使用项目 `.env` 文件

```powershell
Copy-Item .env.example .env
notepad .env
```

写入：

```dotenv
KG_DATABASE_PATH=data/knowledge_graph.db
DEEPSEEK_API_KEY=sk-你的新密钥
DEEPSEEK_MODEL=deepseek-flash
```

启动时增加 `--env-file .env`。`.env` 已被 `.gitignore` 忽略，不应上传或发给别人。

> OpenClaw 和本项目是两个独立进程。即使 OpenClaw 已经保存了 DeepSeek Key，本项目仍需要通过环境变量或 `.env` 获得自己的 Key。

## 启动 Agent

使用当前 PowerShell 环境变量启动：

```powershell
cd "$HOME\OneDrive\Desktop\知识图谱agent"
.\.venv\Scripts\python.exe -m uvicorn kg_agent.api.app:app --reload
```

使用 `.env` 文件启动：

```powershell
cd "$HOME\OneDrive\Desktop\知识图谱agent"
.\.venv\Scripts\python.exe -m uvicorn kg_agent.api.app:app --reload --env-file .env
```

看到 `Uvicorn running on http://127.0.0.1:8000` 表示启动成功。不要关闭这个 PowerShell 窗口；停止服务时按 `Ctrl+C`。

### 与 OpenClaw 一起使用

OpenClaw 运行在 WSL 时，推荐让知识图谱 API 也在 WSL 中启动：

```powershell
wsl -d Ubuntu-24.04
```

然后在 Ubuntu 中执行：

```bash
read -rsp "DeepSeek API Key: " DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
export DEEPSEEK_MODEL='deepseek-flash'
echo
cd "/mnt/c/Users/<你的 Windows 用户名>/<项目路径>/knowledge-graph-agent"
bash openclaw/start-kg-api.sh
```

这种输入方式不会在屏幕或 shell 历史中显示密钥。

首次运行会自动创建独立的 Linux 虚拟环境。OpenClaw 插件的安装、验证和测试方法见 [OpenClaw 接入说明](openclaw/README.md)。

## 打开网页控制台

服务启动后访问：

- 网页控制台：<http://127.0.0.1:8000/>
- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

控制台顶部显示“服务正常”说明前后端已经连接。

## 使用方法

### 1. 导入文档

打开“导入文档”页面：

1. 选择 UTF-8 编码的 `.txt` 或 `.md` 文件，或者直接粘贴文本；
2. 确认文档编号，建议使用唯一且能识别版本的名称；
3. 可填写文件路径或原始网页作为来源地址；
4. 点击“开始抽取候选事实”；
5. 等待 DeepSeek 返回，页面会显示候选数量和跳过数量。

项目提供了测试文本：`data/知识图谱测试文本.txt`。重复导入完全相同的事实不会重复创建候选。

### 2. 审核候选事实

打开“审核候选”页面。每张卡片包含源实体、关系、目标实体、置信度和原文引用。只有当关系方向、实体类型和原文证据都正确时才点击“接受”。点击“拒绝”不会创建正式实体和关系。已经审核的候选不能重复审核。

### 3. 浏览正式图谱

打开“图谱浏览”页面：

- 圆形节点代表实体；
- 节点中显示实体类型；
- 连线代表正式关系；
- 点击连线可在右侧查看置信度和原文证据。

图谱页面只展示已经接受的正式事实，不展示待审核和已拒绝候选。

### 4. 向图谱提问

打开“证据问答”页面，输入自然语言问题，例如：

```text
知识图谱 Agent 使用了哪些技术？依据是什么？
```

问答服务只会把已经人工接受、并且关联了原文证据的正式关系提供给 DeepSeek。回答下方会列出使用过的关系和原文引用。如果图谱中没有足够信息，页面会显示“证据不足”，不会使用外部知识补全答案。

服务还会校验模型返回的关系 ID 和证据 ID。模型引用不存在的 ID 时，回答会被拒绝并转为“证据不足”。

## 命令行导入

不打开网页也可以导入文档：

```powershell
cd "$HOME\OneDrive\Desktop\知识图谱agent"
$env:DEEPSEEK_API_KEY="sk-你的密钥"
.\.venv\Scripts\python.exe scripts\ingest_file.py ".\data\知识图谱测试文本.txt"
```

命令会输出处理分块数、新增候选数、跳过事实数和候选 ID。命令行导入同样只产生候选事实，仍需在网页或 API 中审核。

## API 使用说明

### 文档与候选

| 方法 | 地址 | 作用 |
|---|---|---|
| `POST` | `/documents/ingest` | 抽取文档并创建候选事实 |
| `GET` | `/candidates?status=pending` | 查看待审核候选 |
| `GET` | `/candidates?status=accepted` | 查看已接受候选 |
| `GET` | `/candidates?status=rejected` | 查看已拒绝候选 |
| `POST` | `/candidates/{id}/accept` | 接受候选并写入图谱 |
| `POST` | `/candidates/{id}/reject` | 拒绝候选 |

导入请求示例：

```json
{
  "document_id": "architecture-v1.txt",
  "source_uri": "data/architecture-v1.txt",
  "text": "知识图谱 Agent 使用 DeepSeek 抽取实体关系。"
}
```

### 图谱查询

| 方法 | 地址 | 作用 |
|---|---|---|
| `GET` | `/stats` | 实体、关系、证据和候选统计 |
| `GET` | `/graph` | 返回可视化所需的实体、关系和证据 |
| `POST` | `/questions/ask` | 根据已审核事实进行证据约束问答 |
| `GET` | `/entities/search?q=DeepSeek` | 按名称或别名搜索实体 |
| `GET` | `/entities/{id}/neighbors` | 查询实体相邻关系 |
| `GET` | `/paths?source_id=...&target_id=...&max_depth=3` | 查询实体间路径 |

### 手动写入

| 方法 | 地址 | 作用 |
|---|---|---|
| `POST` | `/entities` | 手动创建或更新实体 |
| `POST` | `/relations` | 手动创建关系 |
| `POST` | `/evidence` | 为关系添加证据 |

完整请求字段和在线调试功能位于 `/docs`。

## 数据模型白名单

实体类型：

| 类型 | 含义 |
|---|---|
| `Person` | 人物 |
| `Project` | 项目 |
| `Component` | 系统组件或模块 |
| `Technology` | 技术、框架或数据库 |
| `Decision` | 技术或业务决策 |
| `Document` | 文档 |

关系类型：

| 关系 | 含义 |
|---|---|
| `OWNS` | 负责、拥有 |
| `PART_OF` | 属于、组成部分 |
| `DEPENDS_ON` | 依赖 |
| `USES` | 使用 |
| `DECIDED_BY` | 由某人决定 |
| `AFFECTS` | 影响 |
| `DOCUMENTED_IN` | 记录在某文档中 |

DeepSeek 返回白名单以外的类型或关系时，该事实会被跳过。

## 数据库与备份

默认数据库位置：`data/knowledge_graph.db`。

备份前建议停止服务：

```powershell
Copy-Item ".\data\knowledge_graph.db" ".\data\knowledge_graph-backup.db"
```

如果希望清空测试数据，先停止服务并备份，再手动删除 `data/knowledge_graph.db`。下次启动会自动创建新数据库。删除数据库无法撤销。

## 运行测试

```powershell
cd "$HOME\OneDrive\Desktop\知识图谱agent"
.\.venv\Scripts\python.exe -m pytest tests -q
```

测试使用临时数据库和模拟抽取器，不消耗 DeepSeek Token，也不会修改正式数据库。

## 安全说明

- 本项目是单用户、本机应用，官方启动方式只监听 `127.0.0.1`；不要在未增加 HTTPS、身份验证、权限控制和限流前绑定到 `0.0.0.0` 或公开网络。
- 文档导入最多接受 50,000 个字符和 20 个分块，避免一次请求产生无上限的 DeepSeek 调用。
- 正式图谱、邻居、路径和问答只读取 `accepted` 状态的关系。
- `.env`、SQLite 数据库、虚拟环境、`node_modules` 和构建元数据均不会提交到 Git。
- GitHub Actions 会执行测试、Python/npm 依赖审计和密钥扫描；详细边界和漏洞报告方式见 [SECURITY.md](SECURITY.md)。
- 导入文本和问答证据会发送至 DeepSeek，请勿处理未经授权的敏感数据。

## 常见问题

### 页面显示“连接失败”

确认服务窗口仍然打开，并访问 <http://127.0.0.1:8000/health>。端口被占用时可改用：

```powershell
.\.venv\Scripts\python.exe -m uvicorn kg_agent.api.app:app --port 8001
```

### 提示 `DEEPSEEK_API_KEY is not configured`

当前服务进程没有读到 Key。停止服务，在同一个 PowerShell 窗口设置环境变量后重新启动，或者使用 `--env-file .env`。

### DeepSeek 返回 401

API Key 无效、已删除或复制不完整。创建新 Key，更新环境变量或 `.env` 后重启服务。

### 抽取超时

检查网络和 DeepSeek 余额后重试。超时不会把不完整事实写入正式图谱。

### 问答总是提示“证据不足”

先确认相关候选事实已经在“审核候选”页面被接受，并且关系带有原文证据。问答不会读取待审核事实，也不会根据常识猜测答案。

### 候选数量为 0

原文可能没有明确关系、模型输出不在白名单中，或者证据不是原文逐字引用。可以将文档改写为更明确的事实句后重试。

### OpenClaw 能使用 DeepSeek，但本项目仍提示没有 Key

OpenClaw 把凭据保存在自己的认证存储中，本项目不会直接读取。请为本项目单独设置 `DEEPSEEK_API_KEY`。

## 项目结构

```text
知识图谱agent/
├── data/                         # SQLite 数据库和示例文本
├── docs/                         # 架构、导入流程和路线图
├── openclaw/                     # OpenClaw 接入说明
├── scripts/                      # 文件导入与示例数据脚本
├── src/kg_agent/
│   ├── api/                      # FastAPI 路由与请求模型
│   ├── application/              # 导入、审核、图服务、Agent 编排
│   ├── domain/                   # Entity、Relation、Evidence 等模型
│   ├── infrastructure/           # SQLite 与 DeepSeek 适配器
│   └── ports/                    # 存储和抽取接口
├── tests/                        # 自动测试
├── web/                          # 网页控制台 HTML/CSS/JavaScript
├── .env.example
└── pyproject.toml
```

## 当前限制与后续计划

- 只支持 TXT 和 Markdown；
- 实体消歧使用“类型 + 名称”精确匹配；
- 图谱可视化适合中小规模数据；
- DeepSeek 失败时没有后台重试任务；
- 暂未实现用户登录和多人权限；
- OpenClaw 插件目前只提供只读工具，不允许 Agent 绕过人工审核写入图谱；
- 当前问答会读取最多 100 条带证据关系，尚未加入大规模混合检索。

建议下一阶段依次实现实体合并与别名消歧、PDF/DOCX 解析，以及 Neo4j 和向量检索。

更多资料：

- [架构说明](docs/ARCHITECTURE.md)
- [文档抽取与审核流程](docs/INGESTION.md)
- [开发路线图](docs/ROADMAP.md)
