import time
import logging
from typing import List, Dict, Set
from pathlib import Path
from .rss_fetcher import RssFetcher
from .api_caller import ApiCaller
from .logger import setup_application_logging
from .dedup_store import DedupStore


class Scheduler:
    """
    定时调度器：定时从 RSS 源获取链接并调用 API 写入笔记。
    """

    def __init__(self, delay_seconds: int = 10):
        """
        初始化调度器。

        参数：
        - `delay_seconds: int`：每次 API 调用之间的延迟时间（秒），默认 10 秒

        返回值：
        - 无
        """
        self.logger = logging.getLogger(__name__)
        self.delay_seconds = delay_seconds
        # 在 run 中按需创建依赖，便于测试中 patch
        self.rss_fetcher = None
        self.api_caller = None
        self.processed_links: Set[str] = set()
        store_path = Path.cwd() / 'data' / 'processed_links.json'
        self.dedup_store = DedupStore(store_path)

        if not logging.getLogger().handlers:
            setup_application_logging()

    def run(self, configs: List[Dict], token: str) -> None:
        """
        运行调度器，处理所有 RSS 配置。

        参数：
        - `configs: List[Dict]`：每个配置包含 `rss_url`、`topic_id`、`topic_directory_id`
        - `token: str`：Bearer token 用于 API 认证

        返回值：
        - 无
        """
        self.logger.info(f"开始处理 {len(configs)} 个 RSS 配置")

        if not configs:
            self.logger.warning("没有 RSS 配置需要处理")
            return

        if not token:
            self.logger.error("缺少 Bearer token")
            return

        total_processed = 0

        # 按需创建依赖（支持测试 patch）
        rss_fetcher = self.rss_fetcher or RssFetcher()
        api_caller = self.api_caller or ApiCaller()

        for config_index, config in enumerate(configs):
            self.logger.info(f"处理配置 {config_index + 1}/{len(configs)}: {config.get('rss_url', 'Unknown')}")
            try:
                if not all(key in config for key in ['rss_url', 'topic_id', 'topic_directory_id']):
                    self.logger.error(f"配置缺少必要字段: {config}")
                    continue

                rss_url = config['rss_url']
                topic_id = config['topic_id']
                topic_directory_id = config['topic_directory_id']

                self.logger.info(f"从 RSS 源获取链接: {rss_url}")

        
                links = rss_fetcher.fetch_links(rss_url, max_links=10)

                if not links:
                    self.logger.warning(f"RSS 源没有获取到链接: {rss_url}")
                    continue

                self.logger.info(f"获取到 {len(links)} 个链接")

                processed_count = 0
                for link in links:
                    if link in self.processed_links:
                        self.logger.debug(f"跳过已处理的链接: {link}")
                        continue
                    # 写入前持久化去重检查，跨运行避免重复提交
                    if self.dedup_store.has(topic_id, link):
                        self.logger.info(f"跳过历史已写入的链接: {link}")
                        continue

                    try:
                        self.logger.info(f"处理链接: {link}")
                        response = api_caller.call_api(
                            link=link,
                            topic_id=topic_id,
                            topic_directory_id=topic_directory_id,
                            token=token,
                        )
                        if response.ok:
                            self.logger.info(f"成功添加链接到笔记: {link}")
                            self.processed_links.add(link)
                            self.dedup_store.add(topic_id, link)
                            processed_count += 1
                            total_processed += 1
                        else:
                            self.logger.warning(
                                f"添加链接失败，状态码: {response.status_code}, 链接: {link}"
                            )
                            if response.status_code == 409:
                                self.logger.info(f"服务端判定为重复，记录到去重存储: {link}")
                                self.processed_links.add(link)
                                self.dedup_store.add(topic_id, link)

                        if processed_count < len(links):
                            self.logger.info(f"等待 {self.delay_seconds} 秒后继续处理下一个链接...")
                            time.sleep(self.delay_seconds)
                    except Exception as e:
                        self.logger.error(f"处理链接失败: {link}, 错误: {str(e)}")
                        continue

                self.logger.info(f"配置处理完成，共处理 {processed_count} 个新链接")
            except Exception as e:
                self.logger.error(f"处理配置失败: {config}, 错误: {str(e)}")
                continue

        self.logger.info(f"所有 RSS 配置同步完成！总共处理 {total_processed} 个新链接")
        print("所有 RSS 配置同步完成")

    def get_stats(self) -> Dict:
        """
        获取调度器统计信息。

        参数：
        - 无

        返回值：
        - `Dict`：包含 `processed_links_count` 与 `delay_seconds`
        """
        return {
            'processed_links_count': len(self.processed_links),
            'delay_seconds': self.delay_seconds,
        }
