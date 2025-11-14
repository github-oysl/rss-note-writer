from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import os
from pathlib import Path

from ..repositories import init_db_schema, ConfigRepository, ProcessedLinkRepository, WriteResultRepository
from ..api_caller import ApiCaller
from ..scheduler import Scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import threading
from dotenv import load_dotenv


app = FastAPI(title="RSS Note Writer 管理界面")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def ensure_db() -> None:
    """
    确保数据库表结构已初始化。
    """
    init_db_schema()


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


def _run_sync_for_config_id(config_id: int) -> None:
    """
    执行单个配置的同步任务。

    从数据库读取指定配置，使用环境变量中的 `BEARER_TOKEN`，调用调度器执行同步。
    """
    ensure_db()
    repo = ConfigRepository()
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
    ensure_db()
    _reload_bg_scheduler()


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
    repo = ConfigRepository()
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
    repo = ProcessedLinkRepository()
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
