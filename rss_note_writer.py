#!/usr/bin/env python3
"""
RSS Note Writer - 主脚本

从 RSS 源获取文章链接并自动添加到笔记应用中。
"""

import argparse
import sys
import os
from pathlib import Path
import json

# 将当前目录添加到 Python 路径，确保可以导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

 

def create_default_config():
    """
    创建默认配置文件。
    """
    config_dir = Path(__file__).resolve().parent / "config"
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "rss_configs.json"
    if not config_file.exists():
        default_config = [
            {
                "rss_url": "https://rss.cnn.com/rss/edition.rss",
                "topic_id": "cnn_news",
                "topic_directory_id": "news_directory"
            }
        ]
        
        import json
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        print(f"创建默认配置文件: {config_file}")
        return True
    
    return False

def create_default_env():
    """
    创建默认环境变量文件。
    """
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("# 笔记 API 的 Bearer Token\n")
            f.write("BEARER_TOKEN=your_bearer_token_here\n")
            f.write("\n")
            f.write("# 可选：日志级别 (DEBUG, INFO, WARNING, ERROR)\n")
            f.write("# LOG_LEVEL=INFO\n")
            f.write("\n")
            f.write("# 可选：日志文件路径\n")
            f.write("# LOG_FILE=rss_note_writer.log\n")
        
        print(f"创建默认环境文件: {env_file}")
        print("请编辑 .env 文件，设置您的 BEARER_TOKEN")
        return True
    
    return False

def main():
    """
    主函数：解析参数、加载配置、运行调度器。
    """
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="RSS Note Writer - 自动从 RSS 源获取链接并添加到笔记应用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python rss_note_writer.py                    # 使用默认配置
  python rss_note_writer.py --delay 5          # 设置 5 秒延迟
  python rss_note_writer.py --log-level DEBUG  # 启用调试日志
  python rss_note_writer.py --log-file app.log # 输出日志到文件
        """
    )
    
    parser.add_argument(
        "--config-file",
        type=str,
        default="config/rss_configs.json",
        help="RSS 配置文件路径 (默认: config/rss_configs.json)"
    )
    
    parser.add_argument(
        "--delay",
        type=int,
        default=10,
        help="API 调用之间的延迟时间（秒）(默认: 10)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="日志文件路径（可选）"
    )
    
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="创建默认配置文件并退出"
    )
    
    args = parser.parse_args()
    
    # 创建默认配置文件
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
    
    from config_loader import ConfigLoader
    from scheduler import Scheduler
    from logger import setup_application_logging

    logger = setup_application_logging(
        level=args.log_level,
        log_file=args.log_file
    )
    
    logger.info("=== RSS Note Writer 启动 ===")
    logger.info(f"配置文件: {args.config_file}")
    logger.info(f"延迟时间: {args.delay} 秒")
    logger.info(f"日志级别: {args.log_level}")
    if args.log_file:
        logger.info(f"日志文件: {args.log_file}")
    
    try:
        # 加载配置
        config_loader = ConfigLoader(config_path=args.config_file)
        
        logger.info("加载 RSS 配置...")
        configs = config_loader.load_configs()
        logger.info(f"成功加载 {len(configs)} 个 RSS 配置")
        
        # 加载 Bearer Token
        logger.info("加载 Bearer Token...")
        token = config_loader.load_token()
        logger.info("Bearer Token 加载成功")
        
        # 创建并运行调度器
        logger.info("创建调度器...")
        scheduler = Scheduler(delay_seconds=args.delay)
        
        logger.info("开始 RSS 链接同步...")
        scheduler.run(configs, token)
        
        # 显示统计信息
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
    # 设置全局异常处理
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n用户中断操作，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"程序启动错误: {e}")
        sys.exit(1)
