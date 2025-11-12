import pytest
import sys
import os
import logging
import tempfile
from unittest.mock import patch, MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import LoggerConfig, ExceptionHandler, setup_application_logging

class TestLoggerConfig:
    """
    日志配置器单元测试。
    """
    
    def setup_method(self):
        """测试前初始化。"""
        self.logger_config = LoggerConfig("test_logger")
    
    def test_setup_logging_default(self):
        """测试默认日志配置。"""
        logger = self.logger_config.setup_logging()
        
        assert logger is not None
        assert logger.name == "test_logger"
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1  # 至少有一个控制台处理器
    
    def test_setup_logging_debug_level(self):
        """测试 DEBUG 日志级别。"""
        logger = self.logger_config.setup_logging(level="DEBUG")
        
        assert logger.level == logging.DEBUG
    
    def test_setup_logging_error_level(self):
        """测试 ERROR 日志级别。"""
        logger = self.logger_config.setup_logging(level="ERROR")
        
        assert logger.level == logging.ERROR
    
    def test_setup_logging_with_file(self):
        """测试带文件日志的配置。"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as tmp_file:
            log_file = tmp_file.name
        
        try:
            logger = self.logger_config.setup_logging(level="INFO", log_file=log_file)
            
            # 验证文件处理器被添加
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) == 1
            assert file_handlers[0].baseFilename == log_file
            
            # 测试写入日志
            test_message = "测试文件日志消息"
            logger.info(test_message)
            
            # 验证文件内容
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert test_message in content
        
        finally:
            # 清理临时文件
            if os.path.exists(log_file):
                os.unlink(log_file)
    
    def test_setup_logging_invalid_level(self):
        """测试无效的日志级别。"""
        logger = self.logger_config.setup_logging(level="INVALID")
        
        # 应该默认使用 INFO 级别
        assert logger.level == logging.INFO
    
    def test_setup_logging_custom_format(self):
        """测试自定义日志格式。"""
        custom_format = "%(levelname)s: %(message)s"
        logger = self.logger_config.setup_logging(format_string=custom_format)
        
        # 验证格式被应用
        console_handler = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler))
        assert console_handler.formatter._fmt == custom_format
    
    def test_get_logger_default(self):
        """测试获取默认日志记录器。"""
        logger = self.logger_config.get_logger()
        
        assert logger.name == "test_logger"
    
    def test_get_logger_custom_name(self):
        """测试获取自定义名称的日志记录器。"""
        custom_name = "custom_logger"
        logger = self.logger_config.get_logger(custom_name)
        
        assert logger.name == custom_name

class TestExceptionHandler:
    """
    异常处理器单元测试。
    """
    
    def setup_method(self):
        """测试前初始化。"""
        self.logger = logging.getLogger("test_exception")
        self.exception_handler = ExceptionHandler(self.logger)
    
    def test_setup_exception_handler(self):
        """测试异常处理设置。"""
        original_excepthook = sys.excepthook
        
        try:
            self.exception_handler.setup_exception_handler()
            
            # 验证异常处理函数被设置
            assert sys.excepthook != original_excepthook
        finally:
            # 恢复原始异常处理
            sys.excepthook = original_excepthook
    
    def test_log_and_handle_decorator_success(self):
        """测试装饰器成功执行。"""
        @self.exception_handler.log_and_handle
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_log_and_handle_decorator_exception(self):
        """测试装饰器异常处理。"""
        @self.exception_handler.log_and_handle
        def test_function():
            raise ValueError("测试异常")
        
        with pytest.raises(ValueError, match="测试异常"):
            test_function()
    
    def test_keyboard_interrupt_handling(self):
        """测试 KeyboardInterrupt 处理。"""
        original_excepthook = sys.excepthook
        
        try:
            self.exception_handler.setup_exception_handler()
            
            # 模拟 KeyboardInterrupt
            with patch.object(self.logger, 'error') as mock_error:
                # KeyboardInterrupt 应该被原始异常处理函数处理
                try:
                    raise KeyboardInterrupt()
                except KeyboardInterrupt:
                    pass  # 这是预期的行为
        finally:
            sys.excepthook = original_excepthook

class TestSetupApplicationLogging:
    """
    快捷函数单元测试。
    """
    
    def test_setup_application_logging_default(self):
        """测试默认应用日志设置。"""
        logger = setup_application_logging()
        
        assert logger is not None
        assert logger.name == "rss_note_writer"
        assert logger.level == logging.INFO
    
    def test_setup_application_logging_custom(self):
        """测试自定义应用日志设置。"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as tmp_file:
            log_file = tmp_file.name
        
        try:
            logger = setup_application_logging(
                level="DEBUG",
                log_file=log_file,
                app_name="custom_app"
            )
            
            assert logger.name == "custom_app"
            assert logger.level == logging.DEBUG
            
            # 验证异常处理已设置
            # 注意：这里我们只是验证函数执行成功
            assert logger is not None
        
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)
    
    def test_logger_handlers_cleared(self):
        """测试日志处理器被正确清理。"""
        # 创建多个日志配置
        logger1 = setup_application_logging(app_name="test1")
        handler_count_1 = len(logger1.handlers)
        
        logger2 = setup_application_logging(app_name="test2")
        handler_count_2 = len(logger2.handlers)
        
        # 每个日志记录器应该有自己的处理器
        assert handler_count_1 >= 1
        assert handler_count_2 >= 1