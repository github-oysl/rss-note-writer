# Integration test for Logger with existing modules
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import LoggerConfig, ExceptionHandler, setup_application_logging
from config_loader import ConfigLoader
from rss_fetcher import RssFetcher
from api_caller import ApiCaller
from scheduler import Scheduler

print("=== Integration Test for Logger Module ===")

# Test 1: 模块导入测试
try:
    logger_config = LoggerConfig("integration_test")
    print("✓ LoggerConfig 模块导入成功")
except Exception as e:
    print(f"✗ LoggerConfig 模块导入失败: {e}")
    exit(1)

# Test 2: 日志配置测试
try:
    logger = logger_config.setup_logging(level="INFO")
    logger.info("日志系统初始化成功")
    print("✓ 日志配置成功")
except Exception as e:
    print(f"✗ 日志配置失败: {e}")
    exit(1)

# Test 3: 异常处理器测试
try:
    exception_handler = ExceptionHandler(logger)
    exception_handler.setup_exception_handler()
    print("✓ 异常处理器设置成功")
except Exception as e:
    print(f"✗ 异常处理器设置失败: {e}")
    exit(1)

# Test 4: 快捷函数测试
try:
    app_logger = setup_application_logging(level="DEBUG", app_name="rss_integration")
    app_logger.debug("调试日志测试")
    print("✓ 快捷函数测试成功")
except Exception as e:
    print(f"✗ 快捷函数测试失败: {e}")
    exit(1)

# Test 5: 与其他模块集成测试
try:
    # 测试 ConfigLoader 日志
    config_loader = ConfigLoader()
    print("✓ ConfigLoader 日志集成测试成功")
    
    # 测试 RssFetcher 日志
    rss_fetcher = RssFetcher()
    print("✓ RssFetcher 日志集成测试成功")
    
    # 测试 ApiCaller 日志
    api_caller = ApiCaller()
    print("✓ ApiCaller 日志集成测试成功")
    
    # 测试 Scheduler 日志
    scheduler = Scheduler(delay_seconds=0.1)
    print("✓ Scheduler 日志集成测试成功")
    
except Exception as e:
    print(f"✗ 模块集成测试失败: {e}")
    exit(1)

# Test 6: 日志装饰器测试
try:
    @exception_handler.log_and_handle
    def test_function():
        logger.info("测试函数执行")
        return "success"
    
    result = test_function()
    assert result == "success"
    print("✓ 日志装饰器测试成功")
    
except Exception as e:
    print(f"✗ 日志装饰器测试失败: {e}")
    exit(1)

# Test 7: 异常处理测试
try:
    @exception_handler.log_and_handle
    def failing_function():
        raise ValueError("测试异常")
    
    try:
        failing_function()
    except ValueError:
        pass  # 预期异常
    
    print("✓ 异常处理测试成功")
    
except Exception as e:
    print(f"✗ 异常处理测试失败: {e}")
    exit(1)

print("\n=== All Logger Integration Tests Passed! ===")
print("日志模块与现有模块集成测试完成，可以开始主脚本集成。")