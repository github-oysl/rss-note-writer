import json
import logging
from pathlib import Path
from typing import Dict, Set


class DedupStore:
    """
    持久化去重存储，按 `topic_id` 维度记录已写入的链接，避免重复写入。

    文件结构：`{topic_id: [url1, url2, ...]}`
    """

    def __init__(self, store_path: Path):
        """
        初始化去重存储，加载已有数据或创建空存储。

        参数：
        - `store_path: Path`：JSON 文件路径

        返回值：
        - 无
        """
        self.logger = logging.getLogger(__name__)
        self.store_path = store_path
        self._data: Dict[str, Set[str]] = {}
        self._ensure_dir()
        self._load()

    def has(self, topic_id: str, url: str) -> bool:
        """
        判断指定链接是否已在指定 topic 中记录。

        参数：
        - `topic_id: str`
        - `url: str`

        返回值：
        - `bool`：True 表示已存在
        """
        urls = self._data.get(str(topic_id))
        return bool(urls and url in urls)

    def add(self, topic_id: str, url: str) -> None:
        """
        将链接添加到指定 topic 的去重集合并持久化。

        参数：
        - `topic_id: str`
        - `url: str`

        返回值：
        - 无
        """
        key = str(topic_id)
        if key not in self._data:
            self._data[key] = set()
        if url not in self._data[key]:
            self._data[key].add(url)
            self._save()

    def _ensure_dir(self) -> None:
        """
        确保去重文件所在目录存在。

        参数：
        - 无

        返回值：
        - 无
        """
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"创建去重目录失败: {str(e)}")

    def _load(self) -> None:
        """
        从磁盘加载去重数据到内存集合。

        参数：
        - 无

        返回值：
        - 无
        """
        if not self.store_path.exists():
            self._data = {}
            return
        try:
            text = self.store_path.read_text(encoding='utf-8')
            raw: Dict[str, list] = json.loads(text) if text.strip() else {}
            self._data = {k: set(v or []) for k, v in raw.items()}
        except Exception as e:
            self.logger.error(f"加载去重数据失败: {str(e)}")
            self._data = {}

    def _save(self) -> None:
        """
        将内存集合序列化为 JSON 并写回磁盘。

        参数：
        - 无

        返回值：
        - 无
        """
        try:
            serializable: Dict[str, list] = {k: sorted(list(v)) for k, v in self._data.items()}
            self.store_path.write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except Exception as e:
            self.logger.error(f"保存去重数据失败: {str(e)}")

