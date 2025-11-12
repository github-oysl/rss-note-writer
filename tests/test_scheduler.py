import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler import Scheduler

class TestScheduler:
    """
    定时调度器单元测试。
    """
    
    def setup_method(self):
        """测试前初始化。"""
        self.scheduler = Scheduler(delay_seconds=0.1)  # 缩短延迟时间用于测试
        self.test_configs = [
            {
                'rss_url': 'https://example1.com/rss',
                'topic_id': 'topic1',
                'topic_directory_id': 'dir1'
            },
            {
                'rss_url': 'https://example2.com/rss',
                'topic_id': 'topic2',
                'topic_directory_id': 'dir2'
            }
        ]
        self.test_token = 'test_bearer_token'
    
    def test_run_with_empty_configs(self):
        """测试空配置列表。"""
        with patch.object(self.scheduler.logger, 'warning') as mock_warning:
            self.scheduler.run([], self.test_token)
            mock_warning.assert_called_with("没有 RSS 配置需要处理")
    
    def test_run_with_empty_token(self):
        """测试空 token。"""
        with patch.object(self.scheduler.logger, 'error') as mock_error:
            self.scheduler.run(self.test_configs, "")
            mock_error.assert_called_with("缺少 Bearer token")
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    def test_run_successful_flow(self, mock_api_caller_class, mock_rss_fetcher_class):
        """测试成功的完整流程。"""
        # Mock RssFetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch_links.return_value = [
            'https://article1.com',
            'https://article2.com'
        ]
        mock_rss_fetcher_class.return_value = mock_fetcher
        
        # Mock ApiCaller
        mock_caller = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_caller.call_api.return_value = mock_response
        mock_api_caller_class.return_value = mock_caller
        
        # 运行调度器
        self.scheduler.run(self.test_configs[:1], self.test_token)
        
        # 验证调用
        assert mock_fetcher.fetch_links.called
        assert mock_caller.call_api.call_count == 2  # 两个链接
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    def test_run_with_no_links(self, mock_api_caller_class, mock_rss_fetcher_class):
        """测试 RSS 源没有链接的情况。"""
        # Mock RssFetcher 返回空链接
        mock_fetcher = Mock()
        mock_fetcher.fetch_links.return_value = []
        mock_rss_fetcher_class.return_value = mock_fetcher
        
        with patch.object(self.scheduler.logger, 'warning') as mock_warning:
            self.scheduler.run(self.test_configs[:1], self.test_token)
            mock_warning.assert_called_with("RSS 源没有获取到链接: https://example1.com/rss")
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    def test_run_with_api_failure(self, mock_api_caller_class, mock_rss_fetcher_class):
        """测试 API 调用失败的情况。"""
        # Mock RssFetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch_links.return_value = ['https://article1.com']
        mock_rss_fetcher_class.return_value = mock_fetcher
        
        # Mock ApiCaller 返回失败响应
        mock_caller = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_caller.call_api.return_value = mock_response
        mock_api_caller_class.return_value = mock_caller
        
        with patch.object(self.scheduler.logger, 'warning') as mock_warning:
            self.scheduler.run(self.test_configs[:1], self.test_token)
            mock_warning.assert_called()
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    def test_run_with_invalid_config(self, mock_api_caller_class, mock_rss_fetcher_class):
        """测试无效配置的情况。"""
        invalid_config = {'rss_url': 'https://invalid.com/rss'}  # 缺少必要字段
        
        with patch.object(self.scheduler.logger, 'error') as mock_error:
            self.scheduler.run([invalid_config], self.test_token)
            mock_error.assert_called_with("配置缺少必要字段: {'rss_url': 'https://invalid.com/rss'}")
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    def test_run_with_exception_in_config(self, mock_api_caller_class, mock_rss_fetcher_class):
        """测试配置处理抛出异常的情况。"""
        # Mock RssFetcher 抛出异常
        mock_fetcher = Mock()
        mock_fetcher.fetch_links.side_effect = Exception("Network error")
        mock_rss_fetcher_class.return_value = mock_fetcher
        
        with patch.object(self.scheduler.logger, 'error') as mock_error:
            self.scheduler.run(self.test_configs[:1], self.test_token)
            mock_error.assert_called()
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    def test_run_with_duplicate_links(self, mock_api_caller_class, mock_rss_fetcher_class):
        """测试重复链接的处理。"""
        # Mock RssFetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch_links.return_value = [
            'https://duplicate.com/article',
            'https://duplicate.com/article'  # 重复链接
        ]
        mock_rss_fetcher_class.return_value = mock_fetcher
        
        # Mock ApiCaller
        mock_caller = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_caller.call_api.return_value = mock_response
        mock_api_caller_class.return_value = mock_caller
        
        self.scheduler.run(self.test_configs[:1], self.test_token)
        
        # 重复链接应该只处理一次
        assert mock_caller.call_api.call_count == 1
    
    def test_get_stats(self):
        """测试统计信息获取。"""
        # 添加一些已处理的链接
        self.scheduler.processed_links.add('https://test1.com')
        self.scheduler.processed_links.add('https://test2.com')
        
        stats = self.scheduler.get_stats()
        
        assert stats['processed_links_count'] == 2
        assert stats['delay_seconds'] == 0.1
    
    @patch('scheduler.RssFetcher')
    @patch('scheduler.ApiCaller')
    @patch('scheduler.time.sleep')
    def test_delay_between_requests(self, mock_sleep, mock_api_caller_class, mock_rss_fetcher_class):
        """测试请求之间的延迟。"""
        # Mock RssFetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch_links.return_value = [
            'https://article1.com',
            'https://article2.com'
        ]
        mock_rss_fetcher_class.return_value = mock_fetcher
        
        # Mock ApiCaller
        mock_caller = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_caller.call_api.return_value = mock_response
        mock_api_caller_class.return_value = mock_caller
        
        # 运行调度器
        self.scheduler.run(self.test_configs[:1], self.test_token)
        
        # 验证 sleep 被调用（在两个链接之间）
        mock_sleep.assert_called_with(0.1)