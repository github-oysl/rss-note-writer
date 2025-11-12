import os
import feedparser
import logging
from typing import List


class RssFetcher:
    """
    RSS 获取器：负责从 RSS 源中提取文章链接。

    方法：
    - `fetch_links`：拉取并返回过滤后的链接列表
    - `_is_valid_url`：校验链接协议
    - `_normalize_url`：支持 `rsshub://` 前缀的 URL 规范化
    """

    def __init__(self):
        """
        初始化 RSS 获取器。

        参数：
        - 无

        返回值：
        - 无
        """
        self.logger = logging.getLogger(__name__)

    def fetch_links(self, rss_url: str, max_links: int = 10) -> List[str]:
        """
        从指定的 RSS URL 获取文章链接列表。

        参数：
        - `rss_url: str`：RSS 源地址，支持标准 http/https，兼容 `rsshub://` 前缀
        - `max_links: int`：最多返回的链接数量，默认为 10

        返回值：
        - `List[str]`：链接列表，过滤非 http/https 协议

        异常：
        - 异常将被捕获并记录，函数返回空列表
        """
        normalized_url = self._normalize_url(rss_url)
        self.logger.info(f"开始获取 RSS 链接: {rss_url} -> {normalized_url}")

        try:
            feed = feedparser.parse(normalized_url)
            if not feed or not hasattr(feed, 'entries'):
                self.logger.warning(f"RSS 源无效或无内容: {rss_url}")
                return []

            links = []
            for entry in feed.entries:
                if len(links) >= max_links:
                    break
                link = getattr(entry, 'link', None)
                if link and self._is_valid_url(link):
                    links.append(link)
                    self.logger.debug(f"提取到链接: {link}")

            self.logger.info(f"成功获取 {len(links)} 个链接")
            return links
        except Exception as e:
            self.logger.error(f"获取 RSS 链接失败: {rss_url}, 错误: {str(e)}")
            return []

    def _is_valid_url(self, url: str) -> bool:
        """
        验证 URL 是否为有效的 http/https 协议。

        参数：
        - `url: str`：待验证的 URL

        返回值：
        - `bool`：是否有效
        """
        if not url or not isinstance(url, str):
            return False

        url_lower = url.lower().strip()
        return url_lower.startswith('http://') or url_lower.startswith('https://')

    def _normalize_url(self, url: str) -> str:
        """
        规范化 RSS URL。

        规则：
        - `rsshub://` 开头映射到 `RSSHUB_BASE_URL`（默认 `https://rsshub.app`）并拼接路径
        - 其他情况原样返回

        参数：
        - `url: str`：原始 RSS 地址

        返回值：
        - `str`：可用于请求的标准 http/https 地址
        """
        if not url or not isinstance(url, str):
            return url

        url_str = url.strip()
        if url_str.lower().startswith('rsshub://'):
            base = os.getenv('RSSHUB_BASE_URL', 'https://rsshub.app').rstrip('/')
            path = url_str[len('rsshub://'):].lstrip('/')
            return f"{base}/{path}"

        return url_str

