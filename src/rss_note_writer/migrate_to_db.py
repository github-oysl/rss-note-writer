import json
from pathlib import Path
from typing import List, Dict, Any
from .repositories import init_db_schema, ConfigRepository, ProcessedLinkRepository


def import_rss_configs(config_path: Path) -> int:
    """
    将 `rss_configs.json` 导入到数据库表 `rss_config_sources`。

    参数:
    - `config_path`: 配置文件路径

    返回值:
    - `int`: 成功导入条数
    """
    if not config_path.exists():
        return 0
    data = json.loads(config_path.read_text(encoding="utf-8"))
    repo = ConfigRepository()
    count = 0
    for item in data:
        required = all(k in item for k in ("rss_url", "topic_id", "topic_directory_id"))
        if not required:
            continue
        repo.upsert(item)
        count += 1
    return count


def import_processed_links(store_path: Path) -> int:
    """
    将 `processed_links.json` 导入到数据库表 `processed_links`。

    参数:
    - `store_path`: 去重存储 JSON 路径，结构为 `{topic_id: [url...]}`

    返回值:
    - `int`: 成功导入条数
    """
    if not store_path.exists():
        return 0
    data = json.loads(store_path.read_text(encoding="utf-8"))
    repo = ProcessedLinkRepository()
    count = 0
    for topic_id, urls in data.items():
        if not isinstance(urls, list):
            continue
        for url in urls:
            try:
                repo.add(str(topic_id), url)
                count += 1
            except Exception:
                # 忽略重复与异常，确保最大化导入
                pass
    return count


def main() -> None:
    """
    迁移入口：创建表结构并导入两个 JSON 文件。
    """
    init_db_schema()
    base_dir = Path(__file__).resolve().parent
    cfg_count = import_rss_configs(base_dir / "config" / "rss_configs.json")
    links_count = import_processed_links(base_dir / "data" / "processed_links.json")
    print(f"导入完成：配置 {cfg_count} 条，已处理链接 {links_count} 条")


if __name__ == "__main__":
    main()

