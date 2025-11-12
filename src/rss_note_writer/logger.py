import logging
import sys
from typing import Optional
from datetime import datetime


class LoggerConfig:
    """
    日志配置器：统一配置和管理项目日志。

    方法：
    - `setup_logging`：配置控制台与文件日志
    - `get_logger`：返回指定名称的日志记录器
    """

    def __init__(self, name: str = "rss_note_writer"):
        """
        初始化日志配置器。

        参数：
        - `name: str`：日志记录器名称

        返回值：
        - 无
        """
        self.name = name
        self.logger = None

    def setup_logging(
        self,
        level: str = "INFO",
        log_file: Optional[str] = None,
        format_string: Optional[str] = None,
    ) -> logging.Logger:
        """
        设置日志配置。

        参数：
        - `level: str`：日志级别 (DEBUG, INFO, WARNING, ERROR)
        - `log_file: Optional[str]`：日志文件路径；为 None 时不写文件
        - `format_string: Optional[str]`：自定义日志格式；为 None 使用默认格式

        返回值：
        - `logging.Logger`：配置好的日志记录器
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        log_level = level_map.get(level.upper(), logging.INFO)

        if format_string is None:
            format_string = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

        formatter = logging.Formatter(format_string)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(log_level)
        self.logger.handlers.clear()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        if log_file:
            try:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(log_level)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
                self.logger.info(f"日志将同时写入文件: {log_file}")
            except Exception as e:
                self.logger.warning(f"无法创建日志文件 {log_file}: {e}")

        self.logger.info(f"日志系统初始化完成，级别: {level}")
        return self.logger

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        获取指定名称的日志记录器。

        参数：
        - `name: Optional[str]`：日志记录器名称；None 时使用默认名称

        返回值：
        - `logging.Logger`：日志记录器实例
        """
        if name is None:
            name = self.name
        return logging.getLogger(name)


class ExceptionHandler:
    """
    异常处理器：统一处理未捕获的异常。
    """

    def __init__(self, logger: logging.Logger):
        """
        初始化异常处理器。

        参数：
        - `logger: logging.Logger`：用于记录异常的日志记录器
        """
        self.logger = logger

    def setup_exception_handler(self):
        """
        设置全局异常处理。
        """

        def handle_exception(exc_type, exc_value, exc_traceback):
            """
            处理未捕获的异常。

            参数：
            - `exc_type`：异常类型
            - `exc_value`：异常值
            - `exc_traceback`：异常堆栈
            """
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            self.logger.error("未捕获的异常发生:", exc_info=(exc_type, exc_value, exc_traceback))
            self.logger.error(f"异常类型: {exc_type.__name__}")
            self.logger.error(f"异常信息: {exc_value}")
            self.logger.error("程序因异常终止")

        sys.excepthook = handle_exception
        self.logger.info("全局异常处理已设置")

    def log_and_handle(self, func):
        """
        装饰器：记录函数执行与异常处理。

        参数：
        - `func`：被装饰的函数

        返回值：
        - 包装后的函数
        """

        def wrapper(*args, **kwargs):
            try:
                self.logger.debug(f"开始执行函数: {func.__name__}")
                result = func(*args, **kwargs)
                self.logger.debug(f"函数执行完成: {func.__name__}")
                return result
            except Exception as e:
                self.logger.error(f"函数 {func.__name__} 执行失败: {e}", exc_info=True)
                raise

        return wrapper


def setup_application_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    app_name: str = "rss_note_writer",
) -> logging.Logger:
    """
    快捷函数：设置应用程序日志并启用异常处理。

    参数：
    - `level: str`：日志级别
    - `log_file: Optional[str]`：日志文件路径
    - `app_name: str`：应用名称

    返回值：
    - `logging.Logger`：配置好的日志记录器
    """
    logger_config = LoggerConfig(app_name)
    logger = logger_config.setup_logging(level, log_file)
    exception_handler = ExceptionHandler(logger)
    exception_handler.setup_exception_handler()
    return logger

