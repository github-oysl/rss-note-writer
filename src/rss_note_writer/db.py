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
        timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
        _ENGINE = create_engine(get_db_url(), pool_pre_ping=True, connect_args={"connect_timeout": timeout})
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

