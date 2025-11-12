"""
rss_note_writer 包

提供从 RSS 源获取链接并写入笔记应用的完整实现，包含配置加载、RSS 拉取、API 调用、调度与日志。

导出顶层 API 以保持现有测试与使用方式的兼容：
- main
- create_default_config
- create_default_env
- ConfigLoader
- Scheduler
- setup_application_logging
"""

from .cli import main, create_default_config, create_default_env
from .config_loader import ConfigLoader
from .scheduler import Scheduler
from .logger import setup_application_logging

__all__ = [
    "main",
    "create_default_config",
    "create_default_env",
    "ConfigLoader",
    "Scheduler",
    "setup_application_logging",
]

