from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_session, init_engine
from sqlalchemy import text
from .models import Base, RssConfigSource, ProcessedLink, WriteResult, AppUser, UserToken


def init_db_schema() -> None:
    """
    初始化数据库表结构（如不存在则创建）。

    为便于首次部署与迁移，在应用启动时调用一次。
    """
    init_engine()
    from .db import _ENGINE  # type: ignore
    Base.metadata.create_all(_ENGINE)
    # 兼容性迁移：为 processed_links 增加 rss_url 列（若不存在）
    with _ENGINE.connect() as conn:  # type: ignore
        result = conn.execute(
            text("SELECT 1 FROM information_schema.columns WHERE table_name='processed_links' AND column_name='rss_url'")
        ).fetchone()
        if not result:
            conn.execute(text("ALTER TABLE processed_links ADD COLUMN rss_url TEXT"))
            conn.commit()
        # 为三张业务表增加 user_id 列（若不存在），并设置默认值为会话变量
        for tbl in ("rss_config_sources", "processed_links", "write_results"):
            has_user_id = conn.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name='user_id'"), {"t": tbl}).fetchone()
            if not has_user_id:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN user_id BIGINT"))
                # 设置默认值依赖会话变量，插入时若未提供将自动填充
                try:
                    conn.execute(text(f"ALTER TABLE {tbl} ALTER COLUMN user_id SET DEFAULT (current_setting('app.current_user_id', true))::bigint"))
                except Exception:
                    pass
                conn.commit()
        # 外键约束（如存在则忽略）
        for tbl, cname in (("rss_config_sources", "fk_cfg_user"), ("processed_links", "fk_pl_user"), ("write_results", "fk_wr_user")):
            try:
                conn.execute(text(f"ALTER TABLE {tbl} ADD CONSTRAINT {cname} FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE"))
            except Exception:
                pass
        # 启用RLS（若未启用）并创建策略（若未存在）
        for tbl in ("app_users", "user_tokens", "rss_config_sources", "processed_links", "write_results"):
            try:
                conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
            except Exception:
                pass
        # 创建策略（存在则忽略异常）
        policies = [
            ("app_users", "p_users_select", "FOR SELECT USING (id = current_setting('app.current_user_id', true)::bigint)"),
            ("user_tokens", "p_tokens_rw", "FOR ALL USING (user_id = current_setting('app.current_user_id', true)::bigint) WITH CHECK (user_id = current_setting('app.current_user_id', true)::bigint)"),
            ("rss_config_sources", "p_cfg_rw", "FOR ALL USING (user_id = current_setting('app.current_user_id', true)::bigint) WITH CHECK (user_id = current_setting('app.current_user_id', true)::bigint)"),
            ("processed_links", "p_pl_rw", "FOR ALL USING (user_id = current_setting('app.current_user_id', true)::bigint) WITH CHECK (user_id = current_setting('app.current_user_id', true)::bigint)"),
            ("write_results", "p_wr_rw", "FOR ALL USING (user_id = current_setting('app.current_user_id', true)::bigint) WITH CHECK (user_id = current_setting('app.current_user_id', true)::bigint)"),
        ]
        for tbl, name, clause in policies:
            try:
                conn.execute(text(f"CREATE POLICY {name} ON {tbl} {clause}"))
            except Exception:
                pass
        # 为 user_tokens 增加唯一约束，确保每个用户仅有一个 token
        try:
            conn.execute(text("ALTER TABLE user_tokens ADD CONSTRAINT uq_user_tokens_user UNIQUE (user_id)"))
        except Exception:
            pass


class ConfigRepository:
    """
    RSS 配置仓库，提供配置项的增删改查。
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def list(self) -> List[Dict[str, Any]]:
        """
        列出所有 RSS 配置项。

        返回值:
        - `List[Dict]`: 配置项列表
        """
        stmt = select(RssConfigSource)
        rows = self.session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": getattr(r, "user_id", None),
                "rss_url": r.rss_url,
                "topic_id": r.topic_id,
                "topic_directory_id": r.topic_directory_id,
                "max_links": r.max_links,
                "content": r.content,
                "cron": r.cron,
                "active": r.active,
            }
            for r in rows
        ]

    def upsert(self, item: Dict[str, Any]) -> int:
        """
        新增或更新一条配置项（以 `rss_url` 唯一约束）。

        参数:
        - `item`: 包含 `rss_url`, `topic_id`, `topic_directory_id`, 可选 `max_links/content/cron/active`

        返回值:
        - `int`: 配置项主键 ID
        """
        # 尝试按 rss_url 查找
        stmt = select(RssConfigSource).where(RssConfigSource.rss_url == item["rss_url"])
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            for k, v in item.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            self.session.commit()
            return existing.id
        rec = RssConfigSource(
            rss_url=item["rss_url"],
            topic_id=item["topic_id"],
            topic_directory_id=item["topic_directory_id"],
            max_links=item.get("max_links", 10),
            content=item.get("content"),
            cron=item.get("cron"),
            active=item.get("active", True),
        )
        self.session.add(rec)
        self.session.commit()
        return rec.id

    def delete(self, config_id: int) -> None:
        """
        删除指定配置项。
        """
        obj = self.session.get(RssConfigSource, config_id)
        if obj:
            self.session.delete(obj)
            self.session.commit()

    def get(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        根据主键查询配置项。
        """
        obj = self.session.get(RssConfigSource, config_id)
        if not obj:
            return None
        return {
            "id": obj.id,
            "rss_url": obj.rss_url,
            "topic_id": obj.topic_id,
            "topic_directory_id": obj.topic_directory_id,
            "max_links": obj.max_links,
            "content": obj.content,
            "cron": obj.cron,
            "active": obj.active,
        }

    def update(self, config_id: int, item: Dict[str, Any]) -> bool:
        """
        更新指定配置项。

        返回值:
        - `bool`: True 表示更新成功
        """
        obj = self.session.get(RssConfigSource, config_id)
        if not obj:
            return False
        for k in ("rss_url", "topic_id", "topic_directory_id", "max_links", "content", "cron", "active"):
            if k in item and hasattr(obj, k):
                setattr(obj, k, item[k])
        self.session.commit()
        return True


class ProcessedLinkRepository:
    """
    已处理链接仓库，提供去重判断与记录。
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def has(self, topic_id: str, url: str) -> bool:
        """
        判断指定链接是否已记录。
        """
        stmt = (
            select(ProcessedLink.id)
            .where(ProcessedLink.topic_id == str(topic_id))
            .where(ProcessedLink.link_url == url)
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def add(self, topic_id: str, url: str, status_code: Optional[int] = None, rss_url: Optional[str] = None) -> int:
        """
        记录一条已处理链接（幂等，存在则忽略）。

        返回值:
        - `int`: 记录主键 ID（已存在返回其 ID）
        """
        # 幂等插入：尝试插入，若违反唯一约束则返回已有 ID
        try:
            rec = ProcessedLink(topic_id=str(topic_id), link_url=url, status_code=status_code, rss_url=rss_url)
            self.session.add(rec)
            self.session.commit()
            return rec.id
        except IntegrityError:
            self.session.rollback()
            stmt = (
                select(ProcessedLink)
                .where(ProcessedLink.topic_id == str(topic_id))
                .where(ProcessedLink.link_url == url)
            )
            existing = self.session.execute(stmt).scalar_one_or_none()
            return existing.id if existing else 0

    def list(self, filters: Optional[Dict[str, Any]] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        分页查询已处理链接。
        """
        stmt = select(ProcessedLink).order_by(ProcessedLink.id.desc())
        filters = filters or {}
        if tid := filters.get("topic_id"):
            stmt = stmt.where(ProcessedLink.topic_id == str(tid))
        if sc := filters.get("status_code"):
            stmt = stmt.where(ProcessedLink.status_code == int(sc))
        if ru := filters.get("rss_url"):
            stmt = stmt.where(ProcessedLink.rss_url == ru)
        rows = self.session.execute(stmt.offset(offset).limit(limit)).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": getattr(r, "user_id", None),
                "topic_id": r.topic_id,
                "link_url": r.link_url,
                "status_code": r.status_code,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "rss_url": r.rss_url,
            }
            for r in rows
        ]

    def bulk_delete(self, ids: List[int]) -> int:
        """
        批量删除指定 processed_links，并清理相关写入结果。

        返回值:
        - `int`: 实际删除的 processed_links 数量
        """
        if not ids:
            return 0
        # 先删除 write_results
        self.session.execute(text("DELETE FROM write_results WHERE processed_link_id = ANY(:ids)"), {"ids": ids})
        # 再删除 processed_links
        res = self.session.execute(text("DELETE FROM processed_links WHERE id = ANY(:ids)"), {"ids": ids})
        self.session.commit()
        return res.rowcount or 0


class WriteResultRepository:
    """
    写入结果仓库，负责存储接口返回映射与原始响应。
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def record(
        self,
        processed_link_id: int,
        raw_response: Dict[str, Any],
        note_id: Optional[str] = None,
        file_id: Optional[str] = None,
        external_ids: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        存储一条写入结果记录，返回其主键 ID。
        """
        rec = WriteResult(
            processed_link_id=processed_link_id,
            raw_response=raw_response,
            note_id=note_id,
            file_id=file_id,
            external_ids=external_ids or {},
        )
        self.session.add(rec)
        self.session.commit()
        return rec.id

    def by_processed_link(self, processed_link_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 `processed_link_id` 查询写入结果详情。
        """
        obj = self.session.get(WriteResult, processed_link_id)
        if not obj:
            return None
        return {
            "id": obj.id,
            "processed_link_id": obj.processed_link_id,
            "user_id": getattr(obj, "user_id", None),
            "note_id": obj.note_id,
            "file_id": obj.file_id,
            "external_ids": obj.external_ids,
            "raw_response": obj.raw_response,
        }


class UserRepository:
    """
    用户仓库：创建/查找应用用户。
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def get_by_external_uid(self, external_uid: int) -> Optional[Dict[str, Any]]:
        obj = self.session.execute(select(AppUser).where(AppUser.external_uid == external_uid)).scalar_one_or_none()
        if not obj:
            return None
        return {
            "id": obj.id,
            "external_uid": obj.external_uid,
            "active": obj.active,
        }

    def get_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        根据手机号查询用户。

        参数:
        - `phone: str`

        返回值:
        - `Optional[Dict]`: 用户字典或 None
        """
        obj = self.session.execute(select(AppUser).where(AppUser.phone == phone)).scalar_one_or_none()
        if not obj:
            return None
        return {
            "id": obj.id,
            "phone": obj.phone,
            "external_uid": obj.external_uid,
            "active": obj.active,
        }

    def upsert_by_external_uid(self, external_uid: int) -> int:
        obj = self.session.execute(select(AppUser).where(AppUser.external_uid == external_uid)).scalar_one_or_none()
        if obj:
            return obj.id
        rec = AppUser(external_uid=external_uid, active=True)
        self.session.add(rec)
        self.session.commit()
        return rec.id


class TokenRepository:
    """
    令牌仓库：保存与读取用户令牌。
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def save(self, user_id: int, token: str, expires_at: Optional[str] = None) -> int:
        row = self.session.execute(
            text(
                """
                INSERT INTO user_tokens (user_id, token, expires_at, created_at)
                VALUES (:uid, :tok, :exp, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                  token = EXCLUDED.token,
                  expires_at = EXCLUDED.expires_at,
                  created_at = EXCLUDED.created_at
                RETURNING id
                """
            ),
            {"uid": int(user_id), "tok": token, "exp": expires_at},
        ).fetchone()
        self.session.commit()
        return int(row[0]) if row and row[0] is not None else 0

    def latest_for_user(self, user_id: int) -> Optional[str]:
        obj = self.session.execute(select(UserToken).where(UserToken.user_id == user_id).order_by(UserToken.id.desc())).scalar_one_or_none()
        return obj.token if obj else None


def backfill_all_to_user(session: Session, user_id: int) -> None:
    """
    将当前数据库中的业务数据与指定用户建立关联。

    参数：
    - `session: Session`：数据库会话
    - `user_id: int`：目标用户ID

    返回值：
    - 无
    """
    for tbl in ("rss_config_sources", "processed_links", "write_results"):
        session.execute(text(f"UPDATE {tbl} SET user_id = :uid"), {"uid": int(user_id)})
    session.commit()
