#!/usr/bin/env python3
"""
RSS Note Writer - 快速测试脚本

快速验证所有模块功能是否正常。
"""

import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_functionality():
    """测试基本功能。"""
    print("=== RSS Note Writer 快速测试 ===")
    
    # 测试 1: 模块导入
    try:
        from config_loader import ConfigLoader
        from rss_fetcher import RssFetcher
        from api_caller import ApiCaller
        from scheduler import Scheduler
        from logger import setup_application_logging
        import rss_note_writer
        print("✓ 所有模块导入成功")
    except ImportError as e:
        print(f"✗ 模块导入失败: {e}")
        return False
    
    # 测试 2: 日志系统
    try:
        logger = setup_application_logging(level="INFO", app_name="quick_test")
        logger.info("日志系统测试成功")
        print("✓ 日志系统正常")
    except Exception as e:
        print(f"✗ 日志系统失败: {e}")
        return False
    
    # 测试 3: 配置加载器
    try:
        config_loader = ConfigLoader()
        print("✓ 配置加载器初始化成功")
    except Exception as e:
        print(f"✗ 配置加载器失败: {e}")
        return False
    
    # 测试 4: RSS 获取器
    try:
        rss_fetcher = RssFetcher()
        print("✓ RSS 获取器初始化成功")
    except Exception as e:
        print(f"✗ RSS 获取器失败: {e}")
        return False
    
    # 测试 5: API 调用器
    try:
        api_caller = ApiCaller()
        print("✓ API 调用器初始化成功")
    except Exception as e:
        print(f"✗ API 调用器失败: {e}")
        return False
    
    # 测试 6: 调度器
    try:
        scheduler = Scheduler(delay_seconds=1)
        stats = scheduler.get_stats()
        print(f"✓ 调度器初始化成功，统计: {stats}")
    except Exception as e:
        print(f"✗ 调度器失败: {e}")
        return False
    
    # 测试 7: 主脚本功能
    try:
        # 测试默认配置创建
        config_created = rss_note_writer.create_default_config()
        print(f"✓ 默认配置创建: {config_created}")
        
        env_created = rss_note_writer.create_default_env()
        print(f"✓ 默认环境文件创建: {env_created}")
    except Exception as e:
        print(f"✗ 主脚本功能失败: {e}")
        return False
    
    print("\n=== 所有基本测试通过！ ===")
    print("✓ 系统功能正常，可以运行主脚本")
    print("\n使用说明:")
    print("1. 编辑 .env 文件，设置您的 BEARER_TOKEN")
    print("2. 编辑 config/rss_configs.json，添加您的 RSS 源")
    print("3. 运行: python rss_note_writer.py")
    print("\n高级选项:")
    print("  python rss_note_writer.py --help  # 查看所有选项")
    print("  python rss_note_writer.py --create-config  # 重新创建配置文件")
    
    return True

if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)