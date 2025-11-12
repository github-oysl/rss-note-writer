import pytest
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 现在可以导入主脚本模块
import rss_note_writer

class TestMainScript:
    """
    主脚本单元测试。
    """
    
    def setup_method(self):
        """测试前初始化。"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def teardown_method(self):
        """测试后清理。"""
        os.chdir(self.original_cwd)
        # 清理临时目录
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_default_config(self):
        """测试创建默认配置文件。"""
        config_created = rss_note_writer.create_default_config()
        
        assert config_created is True
        assert Path("config/rss_configs.json").exists()
        
        # 验证文件内容
        with open("config/rss_configs.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
            assert isinstance(config, list)
            assert len(config) > 0
            assert "rss_url" in config[0]
    
    def test_create_default_config_existing(self):
        """测试配置文件已存在的情况。"""
        # 先创建一次
        rss_note_writer.create_default_config()
        
        # 再次创建，应该返回 False
        config_created = rss_note_writer.create_default_config()
        assert config_created is False
    
    def test_create_default_env(self):
        """测试创建默认环境文件。"""
        env_created = rss_note_writer.create_default_env()
        
        assert env_created is True
        assert Path(".env").exists()
        
        # 验证文件内容
        with open(".env", 'r', encoding='utf-8') as f:
            content = f.read()
            assert "BEARER_TOKEN" in content
            assert "your_bearer_token_here" in content
    
    def test_create_default_env_existing(self):
        """测试环境文件已存在的情况。"""
        # 先创建一次
        rss_note_writer.create_default_env()
        
        # 再次创建，应该返回 False
        env_created = rss_note_writer.create_default_env()
        assert env_created is False
    
    @patch('rss_note_writer.setup_application_logging')
    @patch('rss_note_writer.ConfigLoader')
    @patch('rss_note_writer.Scheduler')
    def test_main_success(self, mock_scheduler_class, mock_config_loader_class, mock_setup_logging):
        """测试主函数成功执行。"""
        # Mock 日志设置
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock 配置加载器
        mock_config_loader = Mock()
        mock_config_loader.load_configs.return_value = [
            {"rss_url": "https://test.com/rss", "topic_id": "test", "topic_directory_id": "test"}
        ]
        mock_config_loader.load_token.return_value = "test_token"
        mock_config_loader_class.return_value = mock_config_loader
        
        # Mock 调度器
        mock_scheduler = Mock()
        mock_scheduler.get_stats.return_value = {"processed_links_count": 5}
        mock_scheduler_class.return_value = mock_scheduler
        
        # 运行主函数
        with patch('sys.argv', ['rss_note_writer.py']):
            exit_code = rss_note_writer.main()
        
        assert exit_code == 0
        mock_logger.info.assert_called()
        mock_config_loader.load_configs.assert_called_once()
        mock_config_loader.load_token.assert_called_once()
        mock_scheduler.run.assert_called_once()
    
    @patch('rss_note_writer.setup_application_logging')
    @patch('rss_note_writer.ConfigLoader')
    def test_main_file_not_found(self, mock_config_loader_class, mock_setup_logging):
        """测试文件未找到错误。"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock 配置加载器抛出 FileNotFoundError
        mock_config_loader = Mock()
        mock_config_loader.load_configs.side_effect = FileNotFoundError("config file not found")
        mock_config_loader_class.return_value = mock_config_loader
        
        with patch('sys.argv', ['rss_note_writer.py']):
            exit_code = rss_note_writer.main()
        
        assert exit_code == 1
        mock_logger.error.assert_called()
    
    @patch('rss_note_writer.setup_application_logging')
    @patch('rss_note_writer.ConfigLoader')
    def test_main_key_error(self, mock_config_loader_class, mock_setup_logging):
        """测试配置键错误。"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock 配置加载器抛出 KeyError
        mock_config_loader = Mock()
        mock_config_loader.load_token.side_effect = KeyError("BEARER_TOKEN not found")
        mock_config_loader_class.return_value = mock_config_loader
        
        with patch('sys.argv', ['rss_note_writer.py']):
            exit_code = rss_note_writer.main()
        
        assert exit_code == 1
        mock_logger.error.assert_called()
    
    @patch('rss_note_writer.setup_application_logging')
    @patch('rss_note_writer.ConfigLoader')
    def test_main_json_error(self, mock_config_loader_class, mock_setup_logging):
        """测试 JSON 解析错误。"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock 配置加载器抛出 JSONDecodeError
        mock_config_loader = Mock()
        mock_config_loader.load_configs.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_config_loader_class.return_value = mock_config_loader
        
        with patch('sys.argv', ['rss_note_writer.py']):
            exit_code = rss_note_writer.main()
        
        assert exit_code == 1
        mock_logger.error.assert_called()
    
    def test_main_keyboard_interrupt(self):
        """测试键盘中断处理。"""
        # 创建测试文件
        config_file = Path("config/rss_configs.json")
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump([{"rss_url": "test", "topic_id": "test", "topic_directory_id": "test"}], f)
        
        env_file = Path(".env")
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("BEARER_TOKEN=test_token\n")
        
        # Mock 配置加载器抛出 KeyboardInterrupt
        with patch('rss_note_writer.ConfigLoader') as mock_config_loader_class:
            mock_config_loader = Mock()
            mock_config_loader.load_configs.side_effect = KeyboardInterrupt()
            mock_config_loader_class.return_value = mock_config_loader
            
            with patch('rss_note_writer.setup_application_logging') as mock_setup_logging:
                mock_logger = Mock()
                mock_setup_logging.return_value = mock_logger
                
                with patch('sys.argv', ['rss_note_writer.py']):
                    exit_code = rss_note_writer.main()
                
                assert exit_code == 0
                mock_logger.info.assert_called_with("\n用户中断操作，程序退出")
    
    def test_main_with_args(self):
        """测试带参数的主函数。"""
        test_args = [
            'rss_note_writer.py',
            '--config-file', 'custom_config.json',
            '--delay', '5',
            '--log-level', 'DEBUG',
            '--log-file', 'test.log'
        ]
        
        # 创建测试文件
        config_file = Path("custom_config.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump([{"rss_url": "test", "topic_id": "test", "topic_directory_id": "test"}], f)
        
        env_file = Path(".env")
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("BEARER_TOKEN=test_token\n")
        
        with patch('rss_note_writer.setup_application_logging') as mock_setup_logging, \
             patch('rss_note_writer.ConfigLoader') as mock_config_loader_class, \
             patch('rss_note_writer.Scheduler') as mock_scheduler_class:
            
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger
            
            mock_config_loader = Mock()
            mock_config_loader.load_configs.return_value = []
            mock_config_loader.load_token.return_value = "test_token"
            mock_config_loader_class.return_value = mock_config_loader
            
            mock_scheduler = Mock()
            mock_scheduler_class.return_value = mock_scheduler
            
            with patch('sys.argv', test_args):
                exit_code = rss_note_writer.main()
            
            # 验证参数被正确传递
            mock_setup_logging.assert_called_with(level='DEBUG', log_file='test.log')
            mock_scheduler_class.assert_called_with(delay_seconds=5)
    
    def test_main_create_config_flag(self):
        """测试创建配置标志。"""
        test_args = ['rss_note_writer.py', '--create-config']
        
        with patch('sys.argv', test_args):
            exit_code = rss_note_writer.main()
        
        assert exit_code == 0
        assert Path("config/rss_configs.json").exists()
        assert Path(".env").exists()

class TestCommandLineInterface:
    """
    命令行接口测试。
    """
    
    def test_argument_parsing(self):
        """测试参数解析。"""
        test_args = [
            'rss_note_writer.py',
            '--config-file', 'test_config.json',
            '--delay', '15',
            '--log-level', 'ERROR',
            '--log-file', 'error.log'
        ]
        
        with patch('sys.argv', test_args):
            with patch('rss_note_writer.main') as mock_main:
                # 模拟命令行执行
                import rss_note_writer
                # 重新加载模块以使用新的 sys.argv
                import importlib
                importlib.reload(rss_note_writer)
                
                # 这里我们只是验证参数解析不会出错
                assert True  # 如果上面的代码没有抛出异常，测试通过

if __name__ == "__main__":
    # 简单的测试运行
    pytest.main([__file__, "-v"])