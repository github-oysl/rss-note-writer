@echo off
setlocal enabledelayedexpansion

REM 项目启动脚本（Windows）
REM 用途：
REM - 自动创建并使用本项目的虚拟环境
REM - 安装依赖与包（可编辑）
REM - 以包入口运行：python -m rss_note_writer
REM 传入的所有参数将透传给应用，例如：
REM   run_windows.bat --log-level DEBUG --config-file src\rss_note_writer\config\rss_configs.json

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set VENV_DIR=.venv
set PY_BIN=%VENV_DIR%\Scripts\python.exe
set PIP_BIN=%VENV_DIR%\Scripts\pip.exe

REM 代理（默认启用，如需禁用：set NO_PROXY=1 && run_windows.bat ...）
if not defined NO_PROXY (
  set HTTP_PROXY=http://127.0.0.1:7897
  set HTTPS_PROXY=http://127.0.0.1:7897
  set ALL_PROXY=http://127.0.0.1:7897
)

if not exist "%PY_BIN%" (
  echo [setup] 创建虚拟环境...
  python -m venv "%VENV_DIR%"
)

echo [setup] 升级 pip...
"%PY_BIN%" -m pip install --upgrade pip

echo [setup] 安装依赖...
"%PIP_BIN%" install -r requirements.txt

echo [setup] 安装包为可编辑模式...
"%PIP_BIN%" install -e .

echo [run] 启动应用...
"%PY_BIN%" -m rss_note_writer %*

endlocal