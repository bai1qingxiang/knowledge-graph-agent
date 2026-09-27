# OpenClaw 接入

本目录包含一个官方 Tool Plugin 格式的 OpenClaw 插件，以及在 WSL 中启动知识图谱 API 的脚本。

## 已提供工具

| 工具 | 权限 | 作用 |
|---|---|---|
| `kg_ask` | 只读 | 使用正式图谱和 Evidence 回答问题 |
| `kg_search` | 只读 | 搜索实体 |
| `kg_neighbors` | 只读 | 查询实体相邻关系 |
| `kg_find_paths` | 只读 | 查询两个实体间的路径 |
| `kg_stats` | 只读 | 查看图谱数据统计 |

插件不会导入文档、审核候选或直接修改图谱。

## 为什么 API 需要在 WSL 中启动

OpenClaw Gateway 运行在 WSL。Windows PowerShell 中监听 `127.0.0.1:8000` 的程序不一定能被 WSL 的 `127.0.0.1` 访问。让 API 也运行在 WSL 后，插件可以稳定地使用默认地址 `http://127.0.0.1:8000`，同时无需把服务绑定到局域网地址。

## 启动知识图谱 API

进入 Ubuntu：

```powershell
wsl -d Ubuntu-24.04
```

在 Ubuntu 中设置 API Key 并启动：

```bash
read -rsp "DeepSeek API Key: " DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
export DEEPSEEK_MODEL='deepseek-flash'
echo
cd "/mnt/c/Users/<你的 Windows 用户名>/<项目路径>/knowledge-graph-agent"
bash openclaw/start-kg-api.sh
```

`read -s` 不会在屏幕或 shell 历史中显示密钥。

首次运行会在 `~/.local/share/knowledge-graph-agent/venv` 创建 Linux 虚拟环境并安装项目。看到 `Uvicorn running on http://127.0.0.1:8000` 后保持该终端打开。

Windows 浏览器仍可访问 <http://127.0.0.1:8000/>。

## 验证插件

另开一个 WSL 终端：

```bash
curl http://127.0.0.1:8000/health
openclaw plugins inspect knowledge-graph-tools
openclaw plugins doctor
openclaw gateway restart
openclaw tui
```

在 TUI 中尝试：

```text
请使用 kg_stats 告诉我知识图谱中有多少实体和关系。
```

图谱中已有审核通过的事实后，可以问：

```text
请调用 kg_ask：知识图谱 Agent 使用了哪些技术？请附上证据。
```

## 插件源码

插件位于 `openclaw/knowledge-graph-tools`，使用 OpenClaw 2026.9.6 官方脚手架生成。开发命令：

```bash
cd "/mnt/c/Users/<你的 Windows 用户名>/<项目路径>/knowledge-graph-agent/openclaw/knowledge-graph-tools"
npm install
npm run plugin:validate
npm test
```
