# Integration test for Scheduler
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scheduler import Scheduler
from config_loader import ConfigLoader
from rss_fetcher import RssFetcher
from api_caller import ApiCaller

print("=== Integration Test for Scheduler ===")

# 测试 1: 模块导入测试
try:
    scheduler = Scheduler(delay_seconds=0.1)
    print("✓ Scheduler 模块导入成功")
except Exception as e:
    print(f"✗ Scheduler 模块导入失败: {e}")
    exit(1)

# 测试 2: 依赖模块测试
try:
    config_loader = ConfigLoader()
    rss_fetcher = RssFetcher()
    api_caller = ApiCaller()
    print("✓ 所有依赖模块导入成功")
except Exception as e:
    print(f"✗ 依赖模块导入失败: {e}")
    exit(1)

# 测试 3: 调度器初始化测试
try:
    assert scheduler.delay_seconds == 0.1
    assert hasattr(scheduler, 'processed_links')
    assert hasattr(scheduler, 'rss_fetcher')
    assert hasattr(scheduler, 'api_caller')
    print("✓ 调度器初始化成功")
except Exception as e:
    print(f"✗ 调度器初始化失败: {e}")
    exit(1)

# 测试 4: 统计信息测试
try:
    stats = scheduler.get_stats()
    assert 'processed_links_count' in stats
    assert 'delay_seconds' in stats
    assert stats['delay_seconds'] == 0.1
    print("✓ 统计信息功能正常")
except Exception as e:
    print(f"✗ 统计信息功能失败: {e}")
    exit(1)

# 测试 5: 空配置测试
try:
    scheduler.run([], "test_token")
    print("✓ 空配置处理正常")
except Exception as e:
    print(f"✗ 空配置处理失败: {e}")
    exit(1)

# 测试 6: 空 token 测试
try:
    scheduler.run([{'rss_url': 'test', 'topic_id': 'test', 'topic_directory_id': 'test'}], "")
    print("✓ 空 token 处理正常")
except Exception as e:
    print(f"✗ 空 token 处理失败: {e}")
    exit(1)

print("\n=== All Integration Tests Passed! ===")
print("调度器模块集成测试完成，可以继续执行后续任务。")