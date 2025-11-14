import time
import logging
from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .rss_fetcher import RssFetcher
from .api_caller import ApiCaller
from .logger import setup_application_logging
from .dedup_store import DedupStore
import os
from .repositories import ProcessedLinkRepository, WriteResultRepository, init_db_schema
from .api_response_parser import extract_ids_from_response_json


class Scheduler:
    """
    定时调度器：定时从 RSS 源获取链接并调用 API 写入笔记。
    """

    def __init__(self, delay_seconds: int = 10, max_workers: int = 4):
        """
        初始化调度器。

        参数：
        - `delay_seconds: int`：每次 API 调用之间的延迟时间（秒），默认 10 秒
        - `max_workers: int`：并发写入的最大工作线程数，默认 4

        返回值：
        - 无
        """
        self.logger = logging.getLogger(__name__)
        self.delay_seconds = delay_seconds
        self.max_workers = max_workers
        # 在 run 中按需创建依赖，便于测试中 patch
        self.rss_fetcher = None
        self.api_caller = None
        self.processed_links: Set[str] = set()
        store_path = Path(__file__).resolve().parent / 'data' / 'processed_links.json'
        self.dedup_store = None
        self.db_links_repo = None
        self.db_results_repo = None
        # 若启用 DB_URL，则初始化数据库仓库用于去重与结果存储
        if os.getenv("DB_URL"):
            try:
                init_db_schema()
                self.db_links_repo = ProcessedLinkRepository()
                self.db_results_repo = WriteResultRepository()
                self.logger.info("数据库去重与结果存储已启用")
            except Exception as e:
                self.logger.warning(f"数据库初始化失败，回退到文件存储: {str(e)}")
                self.dedup_store = DedupStore(store_path)
        else:
            # 未配置数据库时使用本地文件存储
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
                # 每源最大同步条数，默认 10，最大不超过 200
                max_links_cfg = config.get('max_links')
                try:
                    max_links = int(max_links_cfg) if max_links_cfg is not None else 10
                except Exception:
                    max_links = 10
                if max_links < 1:
                    max_links = 1
                if max_links > 200:
                    max_links = 200
                # 每源 content，默认模板
                default_content = "整理这条笔记的核心内容，注意标题 按发布日期-主题-领域-内容进行拼接"
                content = config.get('content') or default_content

                self.logger.info(f"从 RSS 源获取链接: {rss_url}")
                self.logger.info(f"本次最大同步条数: {max_links}")

                
                links = rss_fetcher.fetch_links(rss_url, max_links=max_links)

                if not links:
                    self.logger.warning(f"RSS 源没有获取到链接: {rss_url}")
                    continue

                self.logger.info(f"获取到 {len(links)} 个链接")

                processed_count = 0
                # 并发执行写入，失败不影响其他链接
                futures = {}
                max_workers_cfg = 0
                try:
                    max_workers_cfg = int(config.get('max_workers', 0))
                except Exception:
                    max_workers_cfg = 0
                workers = max_workers_cfg or self.max_workers
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    for link in links:
                        if link in self.processed_links:
                            self.logger.debug(f"跳过已处理的链接: {link}")
                            continue
                        # 去重判断：优先 DB，其次文件；任一存在则跳过
                        already_in_db = False
                        if self.db_links_repo:
                            try:
                                already_in_db = self.db_links_repo.has(topic_id, link)
                            except Exception:
                                already_in_db = False
                        if already_in_db:
                            self.logger.info(f"跳过数据库已记录的链接: {link}")
                            continue
                        if self.dedup_store and self.dedup_store.has(topic_id, link):
                            self.logger.info(f"跳过文件存储已记录的链接: {link}")
                            continue
                        self.logger.info(f"提交写入任务: {link}")
                        future = executor.submit(
                            api_caller.call_api,
                            link,
                            topic_id,
                            topic_directory_id,
                            token,
                            content,
                        )
                        futures[future] = link

                    for future in as_completed(futures):
                        link = futures[future]
                        try:
                            response = future.result()
                            if response.ok:
                                self.logger.info(f"成功添加链接到笔记: {link}")
                                self.processed_links.add(link)
                                # 记录到 DB 或文件
                                pl_id = None
                                if self.db_links_repo:
                                    try:
                                        pl_id = self.db_links_repo.add(topic_id, link, status_code=response.status_code, rss_url=rss_url)
                                    except Exception:
                                        pl_id = None
                                if self.dedup_store:
                                    self.dedup_store.add(topic_id, link)
                                # 解析响应并记录映射
                                try:
                                    resp_json = {}
                                    try:
                                        resp_json = response.json()
                                    except Exception:
                                        resp_json = {"text": response.text}
                                    note_id, file_id, extra = extract_ids_from_response_json(resp_json)
                                    if self.db_results_repo and pl_id:
                                        self.db_results_repo.record(
                                            processed_link_id=pl_id,
                                            raw_response=resp_json,
                                            note_id=note_id,
                                            file_id=file_id,
                                            external_ids=extra,
                                        )
                                except Exception as e:
                                    self.logger.warning(f"响应映射记录失败: {str(e)}")
                                processed_count += 1
                                total_processed += 1
                            else:
                                self.logger.warning(
                                    f"添加链接失败，状态码: {response.status_code}, 链接: {link}"
                                )
                                if response.status_code in (200, 201, 202, 204, 409):
                                    self.logger.info(f"服务端判定为重复，记录到去重存储: {link}")
                                    self.processed_links.add(link)
                                    pl_id = None
                                    if self.db_links_repo:
                                        try:
                                            pl_id = self.db_links_repo.add(topic_id, link, status_code=response.status_code, rss_url=rss_url)
                                        except Exception:
                                            pl_id = None
                                    if self.dedup_store:
                                        self.dedup_store.add(topic_id, link)
                                    # 即便重复也可尝试记录响应体（若返回体提供现有 ID）
                                    try:
                                        resp_json = {}
                                        try:
                                            resp_json = response.json()
                                        except Exception:
                                            resp_json = {"text": response.text}
                                        note_id, file_id, extra = extract_ids_from_response_json(resp_json)
                                        if self.db_results_repo and pl_id:
                                            self.db_results_repo.record(
                                                processed_link_id=pl_id,
                                                raw_response=resp_json,
                                                note_id=note_id,
                                                file_id=file_id,
                                                external_ids=extra,
                                            )
                                    except Exception:
                                        pass
                        except Exception as e:
                            self.logger.error(f"写入任务异常: {link}, 错误: {str(e)}")

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
