from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, BigInteger, Text, Boolean, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime


class Base(DeclarativeBase):
    """
    SQLAlchemy 基类，用于声明 ORM 模型。
    """
    pass


class RssConfigSource(Base):
    """
    RSS 配置来源模型，对应 `rss_config_sources` 表。

    字段:
    - `id`: 主键
    - `rss_url`: RSS 源地址（唯一）
    - `topic_id`: 目标主题 ID
    - `topic_directory_id`: 目标目录 ID
    - `max_links`: 每次处理的最大链接数量（1-200）
    - `content`: 写入的内容模板
    - `cron`: 定时表达式（可选）
    - `active`: 是否启用
    - `created_at`/`updated_at`: 时间戳
    """

    __tablename__ = "rss_config_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    rss_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_directory_id: Mapped[str] = mapped_column(Text, nullable=False)
    max_links: Mapped[int] = mapped_column(Integer, nullable=True, default=10)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    cron: Mapped[str] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ProcessedLink(Base):
    """
    已处理链接模型，对应 `processed_links` 表。

    字段:
    - `id`: 主键
    - `topic_id`: 主题 ID
    - `link_url`: 链接地址
    - `status_code`: 响应状态码（成功/重复/失败等）
    - `processed_at`: 处理时间
    约束:
    - 唯一约束 `(topic_id, link_url)`
    """

    __tablename__ = "processed_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=True)
    rss_url: Mapped[str] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("topic_id", "link_url", name="uq_processed_topic_link"),
    )


class WriteResult(Base):
    """
    写入结果映射模型，对应 `write_results` 表。

    字段:
    - `id`: 主键
    - `processed_link_id`: 关联 `ProcessedLink` 主键
    - `note_id`: 返回的笔记 ID（可选）
    - `file_id`: 返回的文件/附件 ID（可选）
    - `external_ids`: 其他标识集合（jsonb）
    - `raw_response`: 原始响应体（jsonb）
    - `created_at`: 创建时间
    """

    __tablename__ = "write_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    processed_link_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note_id: Mapped[str] = mapped_column(Text, nullable=True)
    file_id: Mapped[str] = mapped_column(Text, nullable=True)
    external_ids: Mapped[dict] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
class AppUser(Base):
    """
    应用用户模型，对应 `app_users` 表。

    字段：
    - `id`：主键
    - `external_uid`：外部系统用户ID（如登录响应中的 uid）
    - `phone`：手机号（可选）
    - `name`：名称（可选）
    - `provider`：来源提供方（默认 'get-notes'）
    - `active`：是否启用
    - `created_at`：创建时间
    """

    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_uid: Mapped[int] = mapped_column(BigInteger, nullable=True)
    phone: Mapped[str] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="get-notes")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class UserToken(Base):
    """
    用户令牌模型，对应 `user_tokens` 表。

    字段：
    - `id`：主键
    - `user_id`：关联应用用户ID
    - `token`：Bearer Token
    - `expires_at`：过期时间（可选）
    - `created_at`：创建时间
    """

    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
