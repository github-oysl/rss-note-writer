import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras


def _load_db_url() -> str:
    """
    加载数据库连接字符串。

    参数：
    - 无

    返回值：
    - str：数据库连接字符串（从环境变量 `DB_URL` 读取）

    异常：
    - KeyError：当未找到 `DB_URL` 时抛出
    """
    # 尝试加载顶层与当前目录的 .env
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    project_root = repo_root.parent
    env_paths = [project_root / ".env", repo_root / ".env", Path.cwd() / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
    url = os.getenv("DB_URL")
    if not url:
        raise KeyError("DB_URL not found in environment")
    return url


def _ensure_dir(p: Path) -> None:
    """
    确保目录存在。

    参数：
    - p: 目标目录路径

    返回值：
    - 无
    """
    p.mkdir(parents=True, exist_ok=True)


def _sql_escape(val: Any) -> str:
    """
    生成安全的 SQL 字面量字符串。

    参数：
    - val: 任意值

    返回值：
    - str：SQL 可用的字面量表示
    """
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        txt = json.dumps(val, ensure_ascii=False)
        return "'" + txt.replace("'", "''") + "'"
    txt = str(val)
    return "'" + txt.replace("'", "''") + "'"


def _batch_insert(table: str, rows: List[Dict[str, Any]], columns: List[str], conflict: Optional[str]) -> List[str]:
    """
    按批生成 INSERT 语句。

    参数：
    - table: 表名
    - rows: 行记录列表
    - columns: 列名顺序
    - conflict: 冲突处理子句（如 "ON CONFLICT (rss_url) DO UPDATE SET ..."），为 None 则不添加

    返回值：
    - List[str]：SQL 语句列表
    """
    sqls: List[str] = []
    if not rows:
        return sqls
    batch = 500
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        values = []
        for r in chunk:
            vals = ", ".join(_sql_escape(r.get(c)) for c in columns)
            values.append(f"({vals})")
        cols = ", ".join(columns)
        base = f"INSERT INTO {table} ({cols}) VALUES \n" + ",\n".join(values)
        if conflict:
            base += "\n" + conflict
        base += ";"
        sqls.append(base)
    return sqls


def export_to_sql() -> None:
    """
    导出当前数据库数据为可在 Neon 执行的 SQL 文件。

    参数：
    - 无

    返回值：
    - 无（在 `export/sql/` 目录生成 .sql 文件与 manifest）

    异常：
    - 连接或读表失败将抛出异常
    """
    db_url = _load_db_url()
    out_dir = Path(__file__).resolve().parent.parent / "export" / "sql"
    _ensure_dir(out_dir)

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        manifest: Dict[str, Any] = {"tables": {}}

        def dump_table(name: str, select_sql: str, columns: List[str], conflict: Optional[str], filename: str) -> None:
            print(f"[export] reading {name}...")
            try:
                cur.execute(select_sql)
                rows = cur.fetchall() or []
                manifest["tables"][name] = {"count": len(rows)}
                sqls = _batch_insert(name, rows, columns, conflict)
                Path(out_dir / filename).write_text("\n\n".join(sqls), encoding="utf-8")
                print(f"[export] {name}: {len(rows)} rows")
            except Exception as e:
                # 回滚事务以清除 aborted 状态
                try:
                    conn.rollback()
                except Exception:
                    pass
                manifest["tables"][name] = {"count": 0, "error": str(e)}
                Path(out_dir / filename).write_text("", encoding="utf-8")
                print(f"[export] {name} failed: {e}")

        # app_users
        dump_table(
            "app_users",
            "SELECT external_uid, phone, name, provider, active, created_at FROM app_users ORDER BY id",
            ["external_uid", "phone", "name", "provider", "active", "created_at"],
            "ON CONFLICT (external_uid) DO UPDATE SET phone = EXCLUDED.phone",
            "app_users.sql",
        )

        # user_tokens
        dump_table(
            "user_tokens",
            "SELECT user_id, token, expires_at, created_at FROM user_tokens ORDER BY id",
            ["user_id", "token", "expires_at", "created_at"],
            None,
            "user_tokens.sql",
        )

        # rss_config_sources
        dump_table(
            "rss_config_sources",
            "SELECT rss_url, topic_id, topic_directory_id, max_links, content, cron, active, created_at, updated_at, COALESCE(user_id, NULL) AS user_id FROM rss_config_sources ORDER BY id",
            [
                "rss_url",
                "topic_id",
                "topic_directory_id",
                "max_links",
                "content",
                "cron",
                "active",
                "created_at",
                "updated_at",
                "user_id",
            ],
            "ON CONFLICT (rss_url) DO UPDATE SET topic_id=EXCLUDED.topic_id, topic_directory_id=EXCLUDED.topic_directory_id, max_links=EXCLUDED.max_links, content=EXCLUDED.content, cron=EXCLUDED.cron, active=EXCLUDED.active, updated_at=EXCLUDED.updated_at",
            "rss_config_sources.sql",
        )

        # processed_links
        dump_table(
            "processed_links",
            "SELECT topic_id, link_url, status_code, rss_url, processed_at, COALESCE(user_id, NULL) AS user_id FROM processed_links ORDER BY id",
            ["topic_id", "link_url", "status_code", "rss_url", "processed_at", "user_id"],
            "ON CONFLICT DO NOTHING",
            "processed_links.sql",
        )

        # write_results
        dump_table(
            "write_results",
            "SELECT processed_link_id, note_id, file_id, external_ids, raw_response, created_at, COALESCE(user_id, NULL) AS user_id FROM write_results ORDER BY id",
            ["processed_link_id", "note_id", "file_id", "external_ids", "raw_response", "created_at", "user_id"],
            None,
            "write_results.sql",
        )

        Path(out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[export] done. manifest at {out_dir / 'manifest.json'}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    export_to_sql()