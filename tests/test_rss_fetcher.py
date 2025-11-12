import pytest
import sys
import os
from rss_note_writer.rss_fetcher import RssFetcher

class TestRssFetcher:
    """
    RSS 获取器单元测试。
    """
    
    def setup_method(self):
        """测试前初始化。"""
        self.fetcher = RssFetcher()
    
    def test_fetch_links_with_valid_rss(self, monkeypatch):
        """测试正常 RSS 源获取链接。"""
        # Mock feedparser.parse 返回有效的 RSS 数据
        mock_feed = type('MockFeed', (), {
            'entries': [
                type('MockEntry', (), {'link': 'https://example.com/article1'}),
                type('MockEntry', (), {'link': 'https://example.com/article2'}),
                type('MockEntry', (), {'link': 'http://example.com/article3'}),
                type('MockEntry', (), {'link': 'invalid-url'}),  # 无效链接
            ]
        })()
        
        monkeypatch.setattr('feedparser.parse', lambda url: mock_feed)
        
        links = self.fetcher.fetch_links('https://example.com/rss', max_links=10)
        
        # 验证结果
        assert len(links) == 3  # 只有有效的 http/https 链接
        assert 'https://example.com/article1' in links
        assert 'https://example.com/article2' in links
        assert 'http://example.com/article3' in links
    
    def test_fetch_links_max_links_limit(self, monkeypatch):
        """测试 max_links 参数限制。"""
        # Mock feedparser.parse 返回多个条目
        mock_feed = type('MockFeed', (), {
            'entries': [
                type('MockEntry', (), {'link': f'https://example.com/article{i}'}) 
                for i in range(20)
            ]
        })()
        
        monkeypatch.setattr('feedparser.parse', lambda url: mock_feed)
        
        links = self.fetcher.fetch_links('https://example.com/rss', max_links=5)
        
        # 验证最多返回 5 个链接
        assert len(links) == 5
    
    def test_fetch_links_invalid_rss(self, monkeypatch):
        """测试无效 RSS 源。"""
        # Mock feedparser.parse 返回无效数据
        monkeypatch.setattr('feedparser.parse', lambda url: None)
        
        links = self.fetcher.fetch_links('https://invalid.com/rss')
        
        # 验证返回空列表
        assert links == []
    
    def test_fetch_links_no_entries(self, monkeypatch):
        """测试 RSS 源无 entries 的情况。"""
        # Mock feedparser.parse 返回无 entries 的数据
        mock_feed = type('MockFeed', (), {})()  # 没有 entries 属性
        
        monkeypatch.setattr('feedparser.parse', lambda url: mock_feed)
        
        links = self.fetcher.fetch_links('https://example.com/rss')
        
        # 验证返回空列表
        assert links == []
    
    def test_fetch_links_entry_without_link(self, monkeypatch):
        """测试 entry 无 link 属性的情况。"""
        # Mock feedparser.parse 返回部分 entry 无 link
        mock_feed = type('MockFeed', (), {
            'entries': [
                type('MockEntry', (), {'link': 'https://example.com/article1'}),
                type('MockEntry', (), {}),  # 无 link 属性
                type('MockEntry', (), {'link': 'https://example.com/article2'}),
            ]
        })()
        
        monkeypatch.setattr('feedparser.parse', lambda url: mock_feed)
        
        links = self.fetcher.fetch_links('https://example.com/rss')
        
        # 验证只返回有 link 的条目
        assert len(links) == 2
        assert 'https://example.com/article1' in links
        assert 'https://example.com/article2' in links
    
    def test_fetch_links_network_error(self, monkeypatch):
        """测试网络异常处理。"""
        # Mock feedparser.parse 抛出异常
        def mock_parse(url):
            raise Exception("Network error")
        
        monkeypatch.setattr('feedparser.parse', mock_parse)
        
        links = self.fetcher.fetch_links('https://example.com/rss')
        
        # 验证异常时返回空列表
        assert links == []
    
    def test_is_valid_url(self):
        """测试 URL 验证函数。"""
        # 有效 URL
        assert self.fetcher._is_valid_url('https://example.com') is True
        assert self.fetcher._is_valid_url('http://example.com') is True
        assert self.fetcher._is_valid_url('HTTPS://EXAMPLE.COM') is True  # 大小写不敏感
        assert self.fetcher._is_valid_url('  https://example.com  ') is True  # 前后空格
        
        # 无效 URL
        assert self.fetcher._is_valid_url('ftp://example.com') is False
        assert self.fetcher._is_valid_url('not-a-url') is False
        assert self.fetcher._is_valid_url('') is False
        assert self.fetcher._is_valid_url(None) is False
        assert self.fetcher._is_valid_url(123) is False  # 非字符串
