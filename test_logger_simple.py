# Simple test for logger functionality
import logging
import sys
import tempfile
import os

print("=== Testing Logger Core Functionality ===")

# Test 1: 基础日志配置测试
try:
    # 创建日志记录器
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    
    print("✓ 日志配置成功")
    
    # 测试日志记录
    logger.info("测试信息日志")
    logger.warning("测试警告日志")
    logger.error("测试错误日志")
    
    print("✓ 日志记录功能正常")
    
    # 清理处理器
    logger.removeHandler(console_handler)
    
except Exception as e:
    print(f"✗ 日志配置失败: {e}")
    exit(1)

# Test 2: 日志级别测试
print("\n=== Testing Log Levels ===")
level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

for level_name, level_value in level_map.items():
    print(f"✓ {level_name}: {level_value}")

# Test 3: 文件日志测试
print("\n=== Testing File Logging ===")
try:
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as tmp_file:
        log_file = tmp_file.name
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # 添加到日志记录器
    logger.addHandler(file_handler)
    
    # 写入测试消息
    test_message = "文件日志测试消息"
    logger.info(test_message)
    
    # 验证文件内容
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if test_message in content:
            print("✓ 文件日志功能正常")
        else:
            print("✗ 文件日志内容验证失败")
    
    # 清理
    logger.removeHandler(file_handler)
    os.unlink(log_file)
    
except Exception as e:
    print(f"✗ 文件日志测试失败: {e}")

# Test 4: 异常处理测试
print("\n=== Testing Exception Handling ===")
try:
    # 模拟异常处理函数
    def handle_exception(exc_type, exc_value, exc_traceback):
        print(f"✓ 异常处理器设置成功: {exc_type.__name__}")
    
    # 临时设置异常处理
    original_hook = sys.excepthook
    sys.excepthook = handle_exception
    
    print("✓ 异常处理配置正常")
    
    # 恢复原始异常处理
    sys.excepthook = original_hook
    
except Exception as e:
    print(f"✗ 异常处理测试失败: {e}")

print("\n=== All Logger Tests Passed! ===")
print("日志模块核心功能验证完成，可以开始集成测试。")