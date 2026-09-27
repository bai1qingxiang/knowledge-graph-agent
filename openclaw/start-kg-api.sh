#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
data_root="${XDG_DATA_HOME:-${HOME}/.local/share}/knowledge-graph-agent"
venv_path="${KG_AGENT_WSL_VENV:-${data_root}/venv}"

if [[ ! -x "${venv_path}/bin/python" ]]; then
  echo "Creating WSL virtual environment at ${venv_path}"
  python3 -m venv "${venv_path}"
fi

if ! "${venv_path}/bin/python" -c "import kg_agent" >/dev/null 2>&1; then
  echo "Installing Knowledge Graph Agent into the WSL virtual environment"
  "${venv_path}/bin/python" -m pip install -e "${project_root}"
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DEEPSEEK_API_KEY is not set in this WSL terminal." >&2
  echo "Run: export DEEPSEEK_API_KEY='your-new-key'" >&2
  exit 2
fi

export KG_DATABASE_PATH="${KG_DATABASE_PATH:-${project_root}/data/knowledge_graph.db}"
export DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-flash}"

exec "${venv_path}/bin/python" -m uvicorn kg_agent.api.app:app \
  --host 127.0.0.1 \
  --port "${KG_AGENT_PORT:-8000}"
