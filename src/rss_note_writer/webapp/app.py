from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import os
from pathlib import Path

from ..repositories import init_db_schema, ConfigRepository, ProcessedLinkRepository, WriteResultRepository
from ..repositories import UserRepository, TokenRepository
from ..repositories import backfill_all_to_user
from ..api_caller import ApiCaller
from ..scheduler import Scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import threading
from dotenv import load_dotenv
from sqlalchemy import text
from urllib.parse import urlparse


app = FastAPI(title="RSS Note Writer 管理界面")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret"))


def ensure_db() -> None:
    """
    确保数据库表结构已初始化。
    """
    try:
        init_db_schema()
    except Exception:
        pass


_bg_scheduler: Optional[BackgroundScheduler] = None
_sync_status: dict[int, dict] = {}


def _load_env_once() -> None:
    """
    加载环境变量文件。
    """
    try:
        load_dotenv(Path.cwd() / ".env")
    except Exception:
        load_dotenv()


def _normalize_token(token: str) -> str:
    """
    规范化 Bearer Token，去除前缀字符串。
    """
    if token.startswith("Bearer "):
        return token[len("Bearer ") :]
    return token


def _decode_jwt_uid(token: str) -> Optional[int]:
    """
    解码JWT获取 `uid`（不验签）。

    参数：
    - `token: str`：Bearer Token

    返回值：
    - `Optional[int]`：uid 或 None

    异常：
    - 解码异常返回 None
    """
    try:
        import base64, json
        payload_b64 = token.split(".")[1]
        padding = '=' * (-len(payload_b64) % 4)
        data = base64.urlsafe_b64decode(payload_b64 + padding)
        obj = json.loads(data.decode("utf-8"))
        uid = obj.get("uid")
        return int(uid) if uid is not None else None
    except Exception:
        return None


def _run_sync_for_config_id(config_id: int) -> None:
    """
    执行单个配置的同步任务。

    从数据库读取指定配置，使用环境变量中的 `BEARER_TOKEN`，调用调度器执行同步。
    """
    ensure_db()
    repo = ConfigRepository()
    _apply_rls_session(repo.session)
    items = [i for i in repo.list() if i.get("id") == config_id]
    if not items:
        _sync_status[config_id] = {"state": "not_found", "message": "配置不存在"}
        return
    it = items[0]
    cfg = {
        "rss_url": it.get("rss_url"),
        "topic_id": it.get("topic_id"),
        "topic_directory_id": it.get("topic_directory_id"),
    }
    if it.get("max_links") is not None:
        cfg["max_links"] = it.get("max_links")
    if it.get("content"):
        cfg["content"] = it.get("content")
    _load_env_once()
    token = os.getenv("BEARER_TOKEN", "")
    token = _normalize_token(token)
    if not token:
        _sync_status[config_id] = {"state": "error", "message": "缺少 BEARER_TOKEN"}
        return
    sch = Scheduler()
    try:
        _sync_status[config_id] = {"state": "running", "message": "正在同步..."}
        sch.run([cfg], token)
        stats = sch.get_stats()
        _sync_status[config_id] = {"state": "done", "message": f"完成，同步 {stats.get('processed_links_count', 0)} 条"}
    except Exception as e:
        _sync_status[config_id] = {"state": "error", "message": str(e)}


def _reload_bg_scheduler() -> None:
    """
    重新加载后台定时调度，从数据库读取所有启用且有 `cron` 的配置，注册定时任务。
    """
    global _bg_scheduler
    ensure_db()
    if _bg_scheduler is None:
        _bg_scheduler = BackgroundScheduler()
        _bg_scheduler.start()
    else:
        try:
            _bg_scheduler.remove_all_jobs()
        except Exception:
            pass
    repo = ConfigRepository()
    _apply_rls_session(repo.session)
    for it in repo.list():
        cron_expr = it.get("cron")
        active = it.get("active", True)
        cid = it.get("id")
        if not cron_expr or not active or not cid:
            continue
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
        except Exception:
            continue
        _bg_scheduler.add_job(
            func=_run_sync_for_config_id,
            trigger=trigger,
            args=[cid],
            id=f"cfg_{cid}",
            replace_existing=True,
        )


@app.on_event("startup")
async def on_startup():
    """
    应用启动事件：初始化数据库并加载后台定时任务。
    """
    _load_env_once()
    threading.Thread(target=ensure_db, daemon=True).start()
    try:
        threading.Thread(target=_reload_bg_scheduler, daemon=True).start()
    except Exception:
        pass


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    首页跳转到配置管理。
    """
    return RedirectResponse(url="/configs")


@app.get("/configs", response_class=HTMLResponse)
async def configs_page(request: Request):
    """
    配置管理页面：展示配置列表与新增表单。
    """
    ensure_db()
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)
    repo = ConfigRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    items = repo.list()
    has_running = False
    for it in items:
        st = _sync_status.get(it.get("id"))
        if st and st.get("state") in ("queued", "running"):
            has_running = True
            break
    return templates.TemplateResponse("configs.html", {"request": request, "items": items, "sync_status": _sync_status, "has_running": has_running})


@app.post("/configs/create")
async def configs_create(
    rss_url: str = Form(...),
    topic_id: str = Form(...),
    topic_directory_id: str = Form(...),
    max_links: Optional[int] = Form(10),
    content: Optional[str] = Form(None),
    cron: Optional[str] = Form(None),
):
    """
    创建或更新一条配置项。
    """
    ensure_db()
    repo = ConfigRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    repo.upsert(
        {
            "rss_url": rss_url,
            "topic_id": topic_id,
            "topic_directory_id": topic_directory_id,
            "max_links": max_links or 10,
            "content": content,
            "cron": cron,
            "active": True,
        }
    )
    _reload_bg_scheduler()
    return RedirectResponse(url="/configs", status_code=303)


@app.post("/configs/delete")
async def configs_delete(config_id: int = Form(...)):
    """
    删除配置项。
    """
    ensure_db()
    repo = ConfigRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    repo.delete(config_id)
    _reload_bg_scheduler()
    return RedirectResponse(url="/configs", status_code=303)


@app.post("/configs/sync")
async def configs_sync(config_id: int = Form(...)):
    """
    手动触发指定配置的同步任务。

    为避免阻塞请求线程，使用后台线程执行同步，并立即重定向到配置页面。
    """
    _sync_status[config_id] = {"state": "queued", "message": "已提交同步任务"}
    t = threading.Thread(target=_run_sync_for_config_id, args=(config_id,), daemon=True)
    t.start()
    return RedirectResponse(url="/configs", status_code=303)


@app.post("/configs/sync_now")
async def configs_sync_now(config_id: int = Form(...)):
    _sync_status[config_id] = {"state": "running", "message": "正在同步..."}
    _run_sync_for_config_id(config_id)
    return RedirectResponse(url="/configs", status_code=303)


@app.get("/configs/edit/{config_id}", response_class=HTMLResponse)
async def configs_edit_page(request: Request, config_id: int):
    """
    配置编辑页面：展示指定配置的可编辑表单。
    """
    ensure_db()
    repo = ConfigRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    item = repo.get(config_id)
    return templates.TemplateResponse("config_edit.html", {"request": request, "item": item, "config_id": config_id})


@app.post("/configs/update")
async def configs_update(
    config_id: int = Form(...),
    rss_url: Optional[str] = Form(None),
    topic_id: Optional[str] = Form(None),
    topic_directory_id: Optional[str] = Form(None),
    max_links: Optional[int] = Form(None),
    content: Optional[str] = Form(None),
    cron: Optional[str] = Form(None),
    active: Optional[bool] = Form(True),
):
    """
    更新指定配置项后返回配置列表。
    """
    ensure_db()
    repo = ConfigRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    payload = {}
    if rss_url is not None:
        payload["rss_url"] = rss_url
    if topic_id is not None:
        payload["topic_id"] = topic_id
    if topic_directory_id is not None:
        payload["topic_directory_id"] = topic_directory_id
    if max_links is not None:
        payload["max_links"] = max_links
    if content is not None:
        payload["content"] = content
    if cron is not None:
        payload["cron"] = cron
    if active is not None:
        payload["active"] = active
    repo.update(config_id, payload)
    _reload_bg_scheduler()
    return RedirectResponse(url="/configs", status_code=303)


@app.get("/auth/check", response_class=HTMLResponse)
async def auth_check(request: Request):
    """
    鉴权测试：调用现有 ApiCaller 的 `validate_auth`。
    """
    _load_env_once()
    token = os.getenv("BEARER_TOKEN", "")
    token = _normalize_token(token)
    caller = ApiCaller()
    ok = caller.validate_auth(token)
    return templates.TemplateResponse("auth_check.html", {"request": request, "ok": ok})


@app.get("/auth/login", response_class=HTMLResponse)
async def auth_login(request: Request):
    """
    已移除嵌入页，重定向到手机号登录页。
    """
    return RedirectResponse(url="/login", status_code=303)


@app.post("/auth/save_token")
async def auth_save_token(token: str = Form(...)):
    """
    保存登录后获取的 `Bearer Token` 至 `.env` 并返回配置页面。（保留兼容，不再作为主登录方式）
    """
    _save_token_to_env(token)
    try:
        uid = _decode_jwt_uid(_normalize_token(token))
        repo_user = UserRepository()
        user_id = repo_user.upsert_by_external_uid(uid or 0)
        # 设定默认手机号（如无设置）
        try:
            from sqlalchemy import text as sqtxt
            sess = repo_user.session
            sess.execute(sqtxt("UPDATE app_users SET phone = COALESCE(phone, :ph) WHERE id = :id"), {"ph": "17773013220", "id": user_id})
            sess.commit()
        except Exception:
            pass
        TokenRepository().save(user_id=user_id, token=_normalize_token(token))
    except Exception:
        pass
    return RedirectResponse(url="/auth/check", status_code=303)


@app.get("/auth/capture_token")
async def auth_capture_token(token: str, uid: Optional[int] = None):
    """
    像素上报：从查询参数接收 token/uid，保存后返回 1x1 PNG。
    """
    try:
        norm = _normalize_token(token)
        up_uid = uid if uid is not None else _decode_jwt_uid(norm)
        repo_user = UserRepository()
        user_id = repo_user.upsert_by_external_uid(int(up_uid or 0))
        # 设定默认手机号（如无设置）
        try:
            from sqlalchemy import text as sqtxt
            sess = repo_user.session
            sess.execute(sqtxt("UPDATE app_users SET phone = COALESCE(phone, :ph) WHERE id = :id"), {"ph": "17773013220", "id": user_id})
            sess.commit()
        except Exception:
            pass
        TokenRepository().save(user_id=user_id, token=norm)
    except Exception:
        pass
    import base64
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBoQf0uE4AAAAASUVORK5CYII=")
    from fastapi.responses import Response
    return Response(content=pixel, media_type="image/png")


@app.post("/admin/backfill_user")
async def admin_backfill_user(phone: str = Form(...), external_uid: Optional[int] = Form(None)):
    """
    管理操作：创建或查找默认用户，并将当前数据库中的数据与其建立关联。
    """
    ensure_db()
    from ..db import get_session
    sess = get_session()
    # 创建/查找用户
    repo_user = UserRepository(sess)
    uid = external_uid if external_uid is not None else 0
    user_id = repo_user.upsert_by_external_uid(uid)
    # 更新手机号
    try:
        sess.execute(text("UPDATE app_users SET phone = :ph WHERE id = :id"), {"ph": phone, "id": user_id})
        sess.commit()
    except Exception:
        pass
    # 关联所有业务数据
    backfill_all_to_user(sess, user_id)
    return JSONResponse({"ok": True, "user_id": user_id})


@app.get("/links", response_class=HTMLResponse)
async def links_page(
    request: Request,
    topic_id: Optional[str] = None,
    status_code: Optional[str] = None,
    rss_url: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    写入数据查看页面：按条件过滤，展示分页列表。
    """
    ensure_db()
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)
    repo = ProcessedLinkRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    filters = {}
    if topic_id:
        filters["topic_id"] = topic_id
    if status_code is not None and status_code != "":
        try:
            filters["status_code"] = int(status_code)
        except Exception:
            filters["status_code"] = None
    if rss_url:
        filters["rss_url"] = rss_url
    items = repo.list(filters=filters, limit=limit, offset=offset)
    return templates.TemplateResponse("links.html", {"request": request, "items": items, "limit": limit, "offset": offset, "topic_id": topic_id, "status_code": status_code, "rss_url": rss_url})


@app.get("/links/{link_id}", response_class=HTMLResponse)
async def link_detail(request: Request, link_id: int):
    """
    写入数据详情：展示映射的 `note_id/file_id` 与原始响应。
    """
    ensure_db()
    repo = WriteResultRepository()
    if not _apply_user_session_from_request(repo.session, request):
        _apply_rls_session(repo.session)
    data = repo.by_processed_link(link_id)
    return templates.TemplateResponse("link_detail.html", {"request": request, "data": data, "link_id": link_id})


@app.get("/api/links")
async def api_links(
    topic_id: Optional[str] = None,
    status_code: Optional[str] = None,
    rss_url: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
):
    """
    返回 JSON 格式的已处理链接列表，支持分页与过滤。

    查询参数:
    - `topic_id`: 过滤指定主题
    - `status_code`: 过滤指定状态码
    - `limit`: 返回条数（默认 1000）
    - `offset`: 偏移量（默认 0）
    """
    ensure_db()
    repo = ProcessedLinkRepository()
    _apply_rls_session(repo.session)
    filters = {}
    if topic_id:
        filters["topic_id"] = topic_id
    if status_code is not None and status_code != "":
        try:
            filters["status_code"] = int(status_code)
        except Exception:
            pass
    if rss_url:
        filters["rss_url"] = rss_url
    items = repo.list(filters=filters, limit=limit, offset=offset)
    return JSONResponse(items)


@app.post("/links/bulk_delete")
async def links_bulk_delete(ids: List[int] = Form(default=[])):
    """
    批量删除写入数据（processed_links），并清理关联的写入结果。
    """
    ensure_db()
    repo = ProcessedLinkRepository()
    try:
        deleted = repo.bulk_delete(ids or [])
    except Exception:
        deleted = 0
    return RedirectResponse(url=f"/links?deleted={deleted}", status_code=303)
def _save_token_to_env(token: str) -> None:
    """
    保存或更新 `.env` 文件中的 `BEARER_TOKEN`。

    参数：
    - `token: str`：Bearer Token，允许包含或不包含前缀 `Bearer `

    返回值：
    - 无

    异常：
    - 文件写入异常将向上抛出
    """
    token = _normalize_token(token)
    env_path = Path.cwd() / ".env"
    lines: List[str] = []
    if env_path.exists():
        text = env_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("BEARER_TOKEN="):
                continue
            lines.append(line)
    lines.append(f"BEARER_TOKEN={token}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.get("/health")
async def health(verbose: bool = False):
    """
    数据库连接健康检查（可选详细日志）。

    参数：
    - verbose: 是否返回详细诊断信息

    返回值：
    - JSON：{
      db_ok: bool,
      error: Optional[str],
      info: Optional[dict]
    }

    异常：
    - 内部异常以字符串形式返回到 `error`
    """
    from ..db import get_session, get_db_url
    logs = []
    info = {}
    ok = False
    err = None
    try:
        db_url = get_db_url()
        parsed = urlparse(db_url)
        info.update({
            "driver": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "database": (parsed.path or "/").lstrip("/"),
        })
        logs.append("start session")
        sess = get_session()
        logs.append("exec SELECT 1")
        sess.execute(text("SELECT 1"))
        logs.append("exec version() and server info")
        row = sess.execute(text("SELECT version(), current_database() AS db"))
        ver, dbname = row.fetchone()
        info["server_version"] = ver
        info["current_database"] = dbname
        ok = True
        logs.append("ok")
    except Exception as e:
        err = str(e)
        logs.append(f"error: {err}")
    payload = {"db_ok": ok, "error": err}
    if verbose:
        payload["info"] = info
        payload["logs"] = logs
    return JSONResponse(payload)
def _apply_rls_session(session) -> None:
    """
    为当前数据库会话设置行级安全的用户上下文。
    从 .env 中读取 `BEARER_TOKEN` 并解码 uid，查找/创建应用用户后设置 `app.current_user_id`。
    """
    try:
        _load_env_once()
        tok = os.getenv("BEARER_TOKEN", "")
        tok = _normalize_token(tok)
        uid = None
        if tok:
            uid = _decode_jwt_uid(tok)
        repo_user = UserRepository(session)
        user_id = None
        if uid is not None:
            user = repo_user.get_by_external_uid(uid)
            if user:
                user_id = user["id"]
            else:
                user_id = repo_user.upsert_by_external_uid(uid)
        if user_id is None:
            # 回退：取最小ID用户
            from sqlalchemy import select
            from ..models import AppUser
            u = session.execute(select(AppUser).order_by(AppUser.id.asc())).scalar_one_or_none()
            user_id = u.id if u else None
        if user_id is not None:
            session.execute(text("SET app.current_user_id = :id"), {"id": int(user_id)})
    except Exception:
        pass

def _apply_user_session_from_request(session, request: Request) -> bool:
    """
    根据会话中的 `user_id` 设置 RLS 上下文。

    返回值:
    - `bool`: True 表示已设置；False 表示未设置
    """
    try:
        uid = request.session.get("user_id")
        if uid:
            session.execute(text("SET app.current_user_id = :id"), {"id": int(uid)})
            return True
    except Exception:
        pass
    return False
@app.get("/admin/db_stats")
async def admin_db_stats(verbose: bool = False):
    """
    数据库统计与 RLS 可见性检查。

    参数：
    - verbose: 是否返回连接解析信息

    返回值：
    - JSON：{
      total_counts: dict,
      rls_counts: dict,
      info: Optional[dict]
    }

    异常：
    - 查询异常返回空对象或错误字符串
    """
    ensure_db()
    from ..db import get_session, get_db_url
    sess = get_session()
    def _count(name: str) -> int:
        try:
            return int(sess.execute(text(f"SELECT COUNT(*) FROM {name}"))).scalar() or 0
        except Exception:
            return 0
    info = {}
    if verbose:
        parsed = urlparse(get_db_url())
        info = {
            "driver": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "database": (parsed.path or "/").lstrip("/"),
        }
    # 总表计数
    totals = {
        "app_users": _count("app_users"),
        "user_tokens": _count("user_tokens"),
        "rss_config_sources": _count("rss_config_sources"),
        "processed_links": _count("processed_links"),
        "write_results": _count("write_results"),
    }
    # RLS 可见计数
    try:
        _apply_rls_session(sess)
    except Exception:
        pass
    rls = {
        "app_users": _count("app_users"),
        "user_tokens": _count("user_tokens"),
        "rss_config_sources": _count("rss_config_sources"),
        "processed_links": _count("processed_links"),
        "write_results": _count("write_results"),
    }
    return JSONResponse({"total_counts": totals, "rls_counts": rls, "info": info if verbose else None})
@app.post("/auth/auto_set_token")
async def auth_auto_set_token(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    token = _normalize_token(str(data.get("token", "")))
    uid_val = data.get("uid")
    if not token:
        return JSONResponse({"ok": False, "error": "missing_token"}, status_code=400)
    try:
        uid = int(uid_val) if uid_val is not None else (_decode_jwt_uid(token) or 0)
    except Exception:
        uid = _decode_jwt_uid(token) or 0
    try:
        repo_user = UserRepository()
        user_id = repo_user.upsert_by_external_uid(int(uid or 0))
        # 绑定默认手机号（如未设置）
        try:
            from sqlalchemy import text as sqtxt
            sess = repo_user.session
            # 如用户请求中带 phone，则使用该手机号；否则使用默认
            phone_set = str(data.get("phone")) if data.get("phone") else "17773013220"
            sess.execute(sqtxt("UPDATE app_users SET phone = COALESCE(phone, :ph) WHERE id = :id"), {"ph": phone_set, "id": user_id})
            sess.commit()
        except Exception:
            pass
        TokenRepository().save(user_id=user_id, token=token)
        return JSONResponse({"ok": True, "user_id": user_id})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    手机号登录页面。
    """
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, phone: str = Form(...)):
    """
    手机号登录提交：手机号存在于用户列表则登录成功，否则失败。
    """
    ensure_db()
    repo_user = UserRepository()
    user = repo_user.get_by_phone(phone)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "手机号不存在，登录失败"}, status_code=401)
    request.session["user_id"] = int(user["id"])
    request.session["phone"] = phone
    return RedirectResponse(url="/configs", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    """
    注销当前登录。
    """
    try:
        request.session.clear()
    except Exception:
        pass
    return RedirectResponse(url="/login", status_code=303)
