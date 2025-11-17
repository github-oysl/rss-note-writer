#!/usr/bin/env bash
set -e

# 项目启动脚本（macOS）
# 用途：
# - 自动创建并使用本项目的虚拟环境
# - 安装依赖与包（可编辑）
# - 以包入口运行：python3 -m rss_note_writer
# 传入的所有参数将透传给应用，例如：
#   ./run_mac.sh --log-level DEBUG --config-file src/rss_note_writer/config/rss_configs.json

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PY_BIN="$VENV_DIR/bin/python3"
PIP_BIN="$VENV_DIR/bin/pip"

# 代理（默认启用，如需禁用：NO_PROXY=1 ./run_mac.sh ...）
if [ -z "$NO_PROXY" ]; then
  export HTTP_PROXY="http://127.0.0.1:7897"
  export HTTPS_PROXY="http://127.0.0.1:7897"
  export ALL_PROXY="http://127.0.0.1:7897"
fi

if [ ! -x "$PY_BIN" ]; then
  echo "[setup] 创建虚拟环境..."
  if [ -x "/opt/homebrew/bin/python3.12" ]; then
    /opt/homebrew/bin/python3.12 -m venv "$VENV_DIR"
  else
    python3 -m venv "$VENV_DIR"
  fi
fi

echo "[setup] 升级 pip..."
"$PY_BIN" -m pip install --upgrade pip

echo "[setup] 安装依赖..."
"$PIP_BIN" install -r requirements.txt

echo "[setup] 安装包为可编辑模式..."
"$PIP_BIN" install -e .

echo "[run] 启动应用..."
"$PY_BIN" -m rss_note_writer "$@"