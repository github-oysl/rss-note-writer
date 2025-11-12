#!/usr/bin/env python3
"""
兼容入口模块

提供与历史测试兼容的顶层 API：
- main
- create_default_config
- create_default_env
- ConfigLoader
- Scheduler
- setup_application_logging
"""

import argparse
import json
import sys
from typing import Optional

from src.rss_note_writer.cli import create_default_config, create_default_env
from src.rss_note_writer.config_loader import ConfigLoader
from src.rss_note_writer.scheduler import Scheduler
from src.rss_note_writer.logger import setup_application_logging


def main(argv: Optional[list] = None) -> int:
    """
    主函数：解析参数、加载配置、运行调度器。

    参数：
    - `argv: Optional[list]`：用于测试的参数列表；为 None 时读取系统参数

    返回值：
    - `int`：进程退出码；0 表示成功，非 0 表示错误

    异常：
    - `FileNotFoundError`、`KeyError`、`json.JSONDecodeError` 按逻辑返回 1
    """
    parser = argparse.ArgumentParser(
        description="RSS Note Writer - 自动从 RSS 源获取链接并添加到笔记应用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            """
使用示例:
  python rss_note_writer.py                    # 使用默认配置
  python rss_note_writer.py --delay 5          # 设置 5 秒延迟
  python rss_note_writer.py --log-level DEBUG  # 启用调试日志
  python rss_note_writer.py --log-file app.log # 输出日志到文件
"""
        ),
    )

    parser.add_argument(
        "--config-file",
        type=str,
        default="config/rss_configs.json",
        help="RSS 配置文件路径 (默认: config/rss_configs.json)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=10,
        help="API 调用之间的延迟时间（秒）(默认: 10)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="日志文件路径（可选）",
    )
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="创建默认配置文件并退出",
    )

    args = parser.parse_args(argv)

    if args.create_config:
        config_created = create_default_config()
        env_created = create_default_env()
        if config_created or env_created:
            print("\n默认配置文件创建完成！")
            print("请编辑以下文件：")
            if config_created:
                print("  - config/rss_configs.json: 添加您的 RSS 源配置")
            if env_created:
                print("  - .env: 设置您的 BEARER_TOKEN")
        else:
            print("配置文件已存在，无需创建")
        return 0

    logger = setup_application_logging(level=args.log_level, log_file=args.log_file)
    logger.info("=== RSS Note Writer 启动 ===")
    logger.info(f"配置文件: {args.config_file}")
    logger.info(f"延迟时间: {args.delay} 秒")
    logger.info(f"日志级别: {args.log_level}")
    if args.log_file:
        logger.info(f"日志文件: {args.log_file}")

    try:
        config_loader = ConfigLoader(config_path=args.config_file)
        logger.info("加载 RSS 配置...")
        configs = config_loader.load_configs()
        logger.info(f"成功加载 {len(configs)} 个 RSS 配置")

        logger.info("加载 Bearer Token...")
        token = config_loader.load_token()
        logger.info("Bearer Token 加载成功")

        logger.info("创建调度器...")
        scheduler = Scheduler(delay_seconds=args.delay)
        logger.info("开始 RSS 链接同步...")
        scheduler.run(configs, token)
        stats = scheduler.get_stats()
        logger.info(f"处理统计: {stats}")
        logger.info("=== RSS Note Writer 完成 ===")
        return 0
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        logger.error("请确保配置文件存在，或使用 --create-config 创建默认配置")
        return 1
    except KeyError as e:
        logger.error(f"配置错误: {e}")
        logger.error("请检查 .env 文件是否包含 BEARER_TOKEN")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误: {e}")
        logger.error("请检查配置文件格式是否正确")
        return 1
    except KeyboardInterrupt:
        logger.info("\n用户中断操作，程序退出")
        return 0
    except Exception as e:
        logger.error(f"程序执行错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n用户中断操作，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"程序启动错误: {e}")
        sys.exit(1)
