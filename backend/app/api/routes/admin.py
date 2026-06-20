from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.enums import AccountStatus, TaskStatus, TaskType
from app.models.flow_account import FlowAccount
from app.models.generation import GenerationTask
from app.models.user import User
from app.schemas.flow_account import (
    FlowAccountCreate,
    FlowAccountOut,
    FlowAccountUpdate,
)
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# ---------------- 账号池 ---------------- #
@router.get("/accounts", response_model=list[FlowAccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(FlowAccount).order_by(FlowAccount.id))).all()
    return [FlowAccountOut.from_account(a) for a in rows]


@router.post("/accounts", response_model=FlowAccountOut, status_code=201)
async def create_account(payload: FlowAccountCreate, db: AsyncSession = Depends(get_db)):
    account = FlowAccount(**payload.model_dump())
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return FlowAccountOut.from_account(account)


@router.patch("/accounts/{account_id}", response_model=FlowAccountOut)
async def update_account(
    account_id: int, payload: FlowAccountUpdate, db: AsyncSession = Depends(get_db)
):
    account = await db.get(FlowAccount, account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
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
