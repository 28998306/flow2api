from datetime import datetime, timedelta, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.core.security import api_key_prefix, generate_api_key, hash_api_key
from app.models.api_key import DownstreamApiKey
from app.models.enums import AccountStatus, ApiKeyStatus, TaskStatus, TaskType
from app.models.flow_account import FlowAccount
from app.models.generation import GenerationTask, GenerationTaskEvent
from app.models.user import User
from app.schemas.api_key import ApiKeyBatchDelete, ApiKeyCreate, ApiKeyCreatedOut, ApiKeyOut, ApiKeyUpdate
from app.schemas.flow_account import (
    FlowAccountBatchDelete,
    FlowAccountBatchImport,
    FlowAccountBatchUpdate,
    FlowAccountCreate,
    FlowAccountImportOut,
    FlowAccountOut,
    FlowAccountUpdate,
)
from app.schemas.generation import BatchPublicIdsIn, TaskDetailOut, TaskEventOut, TaskListOut, TaskOut
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# ---------------- 账号池 ---------------- #
@router.get("/accounts", response_model=list[FlowAccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(FlowAccount).order_by(FlowAccount.id))).all()
    return [FlowAccountOut.from_account(a) for a in rows]


def _slug(text: str) -> str:
    import re

    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip()).strip("_").lower()
    return s or "acc"


def _cookie_expiry(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    cookies = data if isinstance(data, list) else data.get("cookies") if isinstance(data, dict) else None
    if not isinstance(cookies, list):
        return None
    expiries = []
    for item in cookies:
        if not isinstance(item, dict):
            continue
        exp = item.get("expirationDate") or item.get("expires")
        try:
            if exp and float(exp) > 0:
                expiries.append(datetime.fromtimestamp(float(exp), tz=timezone.utc))
        except (TypeError, ValueError, OSError):
            continue
    return min(expiries) if expiries else None


@router.post("/accounts", response_model=FlowAccountOut, status_code=201)
async def create_account(payload: FlowAccountCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    if not data.get("chrome_profile"):
        data["chrome_profile"] = _slug(data["label"])
    if not data.get("cookies_expires_at"):
        data["cookies_expires_at"] = _cookie_expiry(data.get("google_cookies"))
    account = FlowAccount(**data)
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return FlowAccountOut.from_account(account)


@router.post("/accounts/import", response_model=FlowAccountImportOut)
async def import_accounts(payload: FlowAccountBatchImport, db: AsyncSession = Depends(get_db)):
    created = 0
    skipped = 0
    errors: list[str] = []
    for idx, item in enumerate(payload.accounts, start=1):
        data = item.model_dump()
        if not data.get("chrome_profile"):
            data["chrome_profile"] = _slug(data["label"])
        if not data.get("cookies_expires_at"):
            data["cookies_expires_at"] = _cookie_expiry(data.get("google_cookies"))
        exists_stmt = select(FlowAccount).where(FlowAccount.label == data["label"])
        if data.get("email"):
            exists_stmt = exists_stmt.where(FlowAccount.email == data["email"])
        if await db.scalar(exists_stmt):
            skipped += 1
            continue
        try:
            db.add(FlowAccount(**data))
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"第 {idx} 条失败: {exc}")
    await db.flush()
    return FlowAccountImportOut(created=created, skipped=skipped, errors=errors)


@router.post("/accounts/batch-delete")
async def batch_delete_accounts(payload: FlowAccountBatchDelete, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(FlowAccount).where(FlowAccount.id.in_(payload.ids)))).all()
    for row in rows:
        await db.delete(row)
    return {"deleted": len(rows)}


@router.patch("/accounts/batch")
async def batch_update_accounts(payload: FlowAccountBatchUpdate, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(FlowAccount).where(FlowAccount.id.in_(payload.ids)))).all()
    changes = payload.model_dump(exclude={"ids"}, exclude_unset=True)
    for row in rows:
        for k, v in changes.items():
            setattr(row, k, v)
        if changes.get("status") == AccountStatus.active:
            row.cooldown_until = None
    await db.flush()
    return {"updated": len(rows)}


@router.post("/accounts/{account_id}/test")
async def test_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """用账号 ST 纯 HTTP 换 AT,验证凭证是否有效(返回邮箱与过期时间)。"""
    import anyio

    from app.services.flow import token_manager
    from app.services.flow.pool import resolve_proxy

    account = await db.get(FlowAccount, account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    if not account.session_token:
        raise HTTPException(400, "账号缺少 session_token(ST)")
    proxy = resolve_proxy(account)
    try:
        tok = await anyio.to_thread.run_sync(
            lambda: token_manager.get_access_token(account.session_token, force=True, proxy=proxy)
        )
    except token_manager.TokenError as exc:
        raise HTTPException(400, f"ST 无效:{exc}") from exc
    from datetime import datetime, timezone

    if tok.email and not account.email:
        account.email = tok.email
    account.bearer_token = tok.token
    account.last_bearer_refresh = datetime.now(timezone.utc)
    account.bearer_expires_at = datetime.fromtimestamp(tok.expires_at, tz=timezone.utc)
    account.next_refresh_at = datetime.fromtimestamp(
        max(0, tok.expires_at - account.auto_refresh_minutes * 60), tz=timezone.utc
    )
    await db.flush()
    return {
        "ok": True,
        "email": tok.email,
        "expires_at": datetime.fromtimestamp(tok.expires_at, tz=timezone.utc).isoformat(),
    }


@router.patch("/accounts/{account_id}", response_model=FlowAccountOut)
async def update_account(
    account_id: int, payload: FlowAccountUpdate, db: AsyncSession = Depends(get_db)
):
    account = await db.get(FlowAccount, account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "google_cookies" in changes and "cookies_expires_at" not in changes:
        changes["cookies_expires_at"] = _cookie_expiry(changes.get("google_cookies"))
    for k, v in changes.items():
        setattr(account, k, v)
    if payload.status == AccountStatus.active:
        account.cooldown_until = None
    await db.flush()
    await db.refresh(account)
    return FlowAccountOut.from_account(account)


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(FlowAccount, account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    await db.delete(account)


# ---------------- 任务日志 ---------------- #
@router.get("/tasks", response_model=TaskListOut)
async def admin_list_tasks(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    type: TaskType | None = None,
    status: TaskStatus | None = None,
    account_id: int | None = None,
):
    stmt = select(GenerationTask)
    count_stmt = select(func.count()).select_from(GenerationTask)
    filters = []
    if type:
        filters.append(GenerationTask.type == type)
    if status:
        filters.append(GenerationTask.status == status)
    if account_id:
        filters.append(GenerationTask.account_id == account_id)
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = await db.scalar(count_stmt) or 0
    rows = (
        await db.scalars(
            stmt.order_by(GenerationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return TaskListOut(items=[TaskOut.model_validate(i) for i in rows], total=total, page=page, page_size=page_size)


@router.get("/tasks/{public_id}", response_model=TaskDetailOut)
async def admin_get_task(public_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.scalar(select(GenerationTask).where(GenerationTask.public_id == public_id))
    if not task:
        raise HTTPException(404, "任务不存在")
    events = (
        await db.scalars(
            select(GenerationTaskEvent)
            .where(GenerationTaskEvent.task_id == task.id)
            .order_by(GenerationTaskEvent.created_at, GenerationTaskEvent.id)
        )
    ).all()
    data = TaskDetailOut.model_validate(task)
    data.events = [TaskEventOut.model_validate(e) for e in events]
    return data


@router.post("/tasks/batch-delete")
async def batch_delete_tasks(payload: BatchPublicIdsIn, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(select(GenerationTask).where(GenerationTask.public_id.in_(payload.public_ids)))
    ).all()
    for row in rows:
        await db.delete(row)
    return {"deleted": len(rows)}


# ---------------- 下游 API Key ---------------- #
@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(DownstreamApiKey)
            .where(DownstreamApiKey.is_deleted.is_(False))
            .order_by(DownstreamApiKey.id.desc())
        )
    ).all()
    return rows


@router.post("/api-keys", response_model=ApiKeyCreatedOut, status_code=201)
async def create_api_key(payload: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    raw = generate_api_key()
    row = DownstreamApiKey(
        name=payload.name,
        user_id=payload.user_id,
        prefix=api_key_prefix(raw),
        key_hash=hash_api_key(raw),
        scopes=payload.scopes,
        note=payload.note,
        expires_at=payload.expires_at,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    data = ApiKeyOut.model_validate(row).model_dump()
    return ApiKeyCreatedOut(**data, key=raw)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyOut)
async def update_api_key(key_id: int, payload: ApiKeyUpdate, db: AsyncSession = Depends(get_db)):
    row = await db.get(DownstreamApiKey, key_id)
    if not row or row.is_deleted:
        raise HTTPException(404, "API Key 不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(key_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(DownstreamApiKey, key_id)
    if not row:
        raise HTTPException(404, "API Key 不存在")
    row.is_deleted = True
    row.status = ApiKeyStatus.disabled


@router.post("/api-keys/batch-delete")
async def batch_delete_api_keys(payload: ApiKeyBatchDelete, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(DownstreamApiKey).where(
                DownstreamApiKey.id.in_(payload.ids), DownstreamApiKey.is_deleted.is_(False)
            )
        )
    ).all()
    for row in rows:
        row.is_deleted = True
        row.status = ApiKeyStatus.disabled
    return {"deleted": len(rows)}


# ---------------- 用户管理 ---------------- #
@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    rows = (
        await db.scalars(
            select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return rows


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    await db.flush()
    await db.refresh(user)
    return user


# ---------------- 仪表盘 ---------------- #
@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=1)

    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    total_tasks = await db.scalar(select(func.count()).select_from(GenerationTask)) or 0
    active_accounts = await db.scalar(
        select(func.count()).select_from(FlowAccount).where(
            FlowAccount.status == AccountStatus.active
        )
    ) or 0

    by_status = {}
    rows = await db.execute(
        select(GenerationTask.status, func.count()).group_by(GenerationTask.status)
    )
    for st, cnt in rows.all():
        by_status[st.value if hasattr(st, "value") else str(st)] = cnt

    last_24h = await db.scalar(
        select(func.count()).select_from(GenerationTask).where(
            GenerationTask.created_at >= since
        )
    ) or 0

    images_24h = await db.scalar(
        select(func.count()).select_from(GenerationTask).where(
            GenerationTask.created_at >= since, GenerationTask.type == TaskType.image
        )
    ) or 0
    videos_24h = await db.scalar(
        select(func.count()).select_from(GenerationTask).where(
            GenerationTask.created_at >= since, GenerationTask.type == TaskType.video
        )
    ) or 0

    return {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "active_accounts": active_accounts,
        "tasks_by_status": by_status,
        "last_24h_tasks": last_24h,
        "last_24h_images": images_24h,
        "last_24h_videos": videos_24h,
        "running": by_status.get(TaskStatus.running.value, 0),
        "queued": by_status.get(TaskStatus.queued.value, 0),
    }
