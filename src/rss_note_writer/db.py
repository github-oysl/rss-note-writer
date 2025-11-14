from typing import Optional
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def get_db_url() -> str:
    """
    获取数据库连接字符串。

    优先读取环境变量 `DB_URL`，若未设置则回退到默认：
    `postgresql://postgres:st6zv2cx@dbconn.sealosgzg.site:49243/postgres`

    返回值:
    - `str`: 可被 SQLAlchemy 使用的连接字符串
    """
    url = os.getenv(
        "DB_URL",
        "postgresql://postgres:st6zv2cx@dbconn.sealosgzg.site:49243/postgres",
    )
    # 兼容可能传入的 `?directConnection=true` 非标准参数，去除查询串
    if "?" in url and url.startswith("postgresql://"):
        url = url.split("?")[0]
    return url


_ENGINE = None
_SessionLocal = None


def init_engine() -> None:
    """
    初始化 SQLAlchemy 引擎与会话工厂。

    该函数应在应用启动时调用一次，以便后续仓库层复用会话。
    """
    global _ENGINE, _SessionLocal
    if _ENGINE is None:
        _ENGINE = create_engine(get_db_url(), pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


def get_session() -> Session:
    """
    获取一个新的数据库会话对象。

    返回值:
    - `Session`: SQLAlchemy 会话，可用于事务性数据库操作
    """
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal()

