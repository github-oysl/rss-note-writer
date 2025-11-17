import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import text
import sys

# 让脚本在未安装包的情况下也能找到 `src/`
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

# 依赖项目内部数据库初始化与仓库工具
from rss_note_writer.db import get_session
from rss_note_writer.repositories import init_db_schema, backfill_all_to_user, UserRepository


def _load_env() -> None:
    """
    加载环境变量文件 `.env`。

    返回值:
    - 无

    异常:
    - 文件读取异常将被忽略
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(Path.cwd() / ".env")
    except Exception:
        pass


def create_or_update_default_user(phone: str = "17773013220", external_uid: int = 0) -> int:
    """
    创建或更新默认用户，并返回其 `user_id`。

    参数:
    - phone: 默认用户手机号
    - external_uid: 外部系统用户标识，默认 0

    返回值:
    - int: 默认用户的主键 ID

    异常:
    - 数据库连接或提交异常向上抛出
    """
    sess = get_session()
    repo_user = UserRepository(sess)
    user_id = repo_user.upsert_by_external_uid(int(external_uid))
    try:
        sess.execute(text("UPDATE app_users SET phone = :ph WHERE id = :id"), {"ph": phone, "id": user_id})
        sess.commit()
    except Exception:
        sess.rollback()
    return user_id


def _read_sql(path: Path) -> str:
    """
    读取 SQL 文件内容。

    参数:
    - path: SQL 文件路径

    返回值:
    - str: SQL 文本

    异常:
    - 文件不存在或编码错误将向上抛出
    """
    return path.read_text(encoding="utf-8")


def _rewrite_user_tokens_sql(sql_text: str, user_id: int) -> str:
    """
    重写 `user_tokens.sql` 的 `user_id`，将所有值替换为指定用户 ID。

    参数:
    - sql_text: 原始 SQL 文本
    - user_id: 目标用户主键 ID

    返回值:
    - str: 重写后的 SQL 文本

    异常:
    - 无
    """
    # 将 VALUES 子句中的第一个数字替换为 user_id，例如: (2, 'token', ...) -> (<uid>, 'token', ...)
    def repl(match: re.Match) -> str:
        return f"({user_id},"

    return re.sub(r"\(\s*\d+\s*,", repl, sql_text)


def exec_sql(sql_text: str) -> None:
    """
    在当前数据库会话中执行原始 SQL 文本。

    参数:
    - sql_text: 待执行的 SQL 文本

    返回值:
    - 无

    异常:
    - 执行错误将向上抛出
    """
    sess = get_session()
    raw_conn = sess.connection().connection  # psycopg2 connection
    cur = raw_conn.cursor()
    cur.execute(sql_text)
    raw_conn.commit()


def import_from_export_dir(export_dir: Path) -> Tuple[int, int, int, int]:
    """
    从导出目录导入四张表的数据，并执行用户关联与回填。

    导入顺序:
    1. rss_config_sources.sql (包含 ON CONFLICT (rss_url) DO UPDATE)
    2. processed_links.sql (ON CONFLICT DO NOTHING)
    3. write_results.sql (直接 INSERT)
    4. user_tokens.sql (重写为默认用户 ID 后直接 INSERT)

    参数:
    - export_dir: 导出根目录路径（包含 `sql/` 子目录）

    返回值:
    - Tuple[int, int, int, int]: 各表理论导入条数 (cfg_cnt, pl_cnt, wr_cnt, tok_cnt)

    异常:
    - 文件读取或 SQL 执行异常将向上抛出
    """
    # 初始化库表与策略
    init_db_schema()
    # 默认用户
    default_user_id = create_or_update_default_user()

    sql_dir = export_dir / "sql"
    # 读取 manifest 以获取条数预期
    manifest_path = sql_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"tables": {}}
    cfg_cnt = int(manifest.get("tables", {}).get("rss_config_sources", {}).get("count", 0))
    pl_cnt = int(manifest.get("tables", {}).get("processed_links", {}).get("count", 0))
    wr_cnt = int(manifest.get("tables", {}).get("write_results", {}).get("count", 0))
    tok_cnt = int(manifest.get("tables", {}).get("user_tokens", {}).get("count", 0))

    # 逐表导入
    # rss_config_sources
    cfg_sql = _read_sql(sql_dir / "rss_config_sources.sql")
    exec_sql(cfg_sql)

    # processed_links
    pl_sql = _read_sql(sql_dir / "processed_links.sql")
    exec_sql(pl_sql)

    # write_results
    wr_sql = _read_sql(sql_dir / "write_results.sql")
    exec_sql(wr_sql)

    # user_tokens：重写 user_id 为默认用户
    tok_sql_path = sql_dir / "user_tokens.sql"
    if tok_sql_path.exists():
        tok_sql = _read_sql(tok_sql_path)
        tok_sql_rewritten = _rewrite_user_tokens_sql(tok_sql, default_user_id)
        exec_sql(tok_sql_rewritten)

    # 回填三张表的 user_id
    sess = get_session()
    backfill_all_to_user(sess, default_user_id)

    return cfg_cnt, pl_cnt, wr_cnt, tok_cnt


def _count_table(sess, name: str) -> int:
    """
    统计指定表的记录数。

    参数:
    - sess: 数据库会话
    - name: 表名

    返回值:
    - int: 行数

    异常:
    - 查询异常向上抛出
    """
    row = sess.execute(text(f"SELECT COUNT(*) FROM {name}"))
    return int(row.scalar() or 0)


def validate_import(manifest_counts: Dict[str, int], allow_delta: int = 5) -> Dict[str, Any]:
    """
    验证导入结果：按表比对行数并进行 RLS 抽样检查。

    参数:
    - manifest_counts: 期望条数映射，如 {"rss_config_sources": 4, ...}
    - allow_delta: 允许的行数偏差（处理冲突导致的差异）

    返回值:
    - Dict[str, Any]: 验证摘要，包括实际计数与是否通过

    异常:
    - 数据库访问异常向上抛出
    """
    sess = get_session()
    actual = {
        "rss_config_sources": _count_table(sess, "rss_config_sources"),
        "processed_links": _count_table(sess, "processed_links"),
        "write_results": _count_table(sess, "write_results"),
        "user_tokens": _count_table(sess, "user_tokens"),
    }
    ok = True
    diffs: Dict[str, int] = {}
    for k, exp in manifest_counts.items():
        diff = abs(int(exp) - int(actual.get(k, 0)))
        diffs[k] = diff
        if diff > allow_delta:
            ok = False
    return {"ok": ok, "actual": actual, "diffs": diffs}


def rls_check(user_id: int) -> Dict[str, Any]:
    """
    RLS 行级安全检查：设置会话用户上下文后，统计各表可见行数。

    参数:
    - user_id: 默认用户主键 ID

    返回值:
    - Dict[str, Any]: 每表可见的行数统计

    异常:
    - 设置会话变量或查询异常向上抛出
    """
    sess = get_session()
    sess.execute(text("SET app.current_user_id = :id"), {"id": int(user_id)})
    sess.commit()
    visible = {
        "app_users": _count_table(sess, "app_users"),
        "user_tokens": _count_table(sess, "user_tokens"),
        "rss_config_sources": _count_table(sess, "rss_config_sources"),
        "processed_links": _count_table(sess, "processed_links"),
        "write_results": _count_table(sess, "write_results"),
    }
    return visible


def main() -> None:
    """
    导入入口：执行导入、验证与 RLS 检查，并输出摘要。

    环境变量:
    - `DB_URL`: 目标数据库连接字符串（建议设置为 Neon 临时分支的连接）

    返回值:
    - 无

    异常:
    - 任意步骤异常将打印错误并以非零退出码结束
    """
    _load_env()
    try:
        export_root = Path.cwd() / "export"
        cfg_cnt, pl_cnt, wr_cnt, tok_cnt = import_from_export_dir(export_root)
        manifest_counts = {
            "rss_config_sources": cfg_cnt,
            "processed_links": pl_cnt,
            "write_results": wr_cnt,
            "user_tokens": tok_cnt,
        }
        summary = validate_import(manifest_counts)
        default_uid = create_or_update_default_user()
        visible = rls_check(default_uid)
        print(json.dumps({"import_expected": manifest_counts, "validate": summary, "rls_visible": visible}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        raise


if __name__ == "__main__":
    main()