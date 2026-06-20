import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_openai_api_user
from app.core.db import get_db
from app.models.enums import TaskStatus, TaskType
from app.models.generation import GenerationTask
from app.models.user import User
from app.schemas.generation import TaskDetailOut, TaskEventOut
from app.services import quota
from app.services.models_catalog import list_models
from app.workers.celery_app import celery_app  # noqa: F401
from app.workers.tasks import generate_image, generate_video

router = APIRouter(prefix="/v1", tags=["openai-compatible"])


class OpenAIImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    model: str = "nano_banana"
    n: int = Field(default=1, ge=1, le=4)
    size: str = "1024x1024"
    response_format: str = "url"
    extra: dict[str, Any] = Field(default_factory=dict)


class OpenAIVideoRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    model: str = "omni_flash"
    duration: int = Field(default=5, ge=2, le=20)
    size: str = "16:9"
    extra: dict[str, Any] = Field(default_factory=dict)


def _aspect_from_size(size: str, default: str) -> str:
    normalized = size.lower().strip()
    if normalized in {"16:9", "9:16", "1:1"}:
        return normalized
    if "x" in normalized:
        try:
            w, h = [int(x) for x in normalized.split("x", 1)]
            if w == h:
                return "1:1"
            return "16:9" if w > h else "9:16"
        except ValueError:
            return default
    return default


async def _create_openai_task(
    db: AsyncSession,
    user: User,
    task_type: TaskType,
    prompt: str,
    params: dict[str, Any],
    amount: int,
) -> GenerationTask:
    await quota.check_rate_limit(user.id)
    limit = user.daily_image_quota if task_type == TaskType.image else user.daily_video_quota
    await quota.consume_quota(user.id, task_type, limit, amount=amount)
    task = GenerationTask(
        public_id=str(uuid.uuid4()),
        user_id=user.id,
        type=task_type,
        status=TaskStatus.queued,
        prompt=prompt,
        params=params,
        outputs=[],
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.get("/models")
async def openai_models(user: User = Depends(get_openai_api_user)):
    return {"object": "list", "data": list_models()}


@router.post("/images/generations")
async def openai_image_generation(
    payload: OpenAIImageRequest,
    user: User = Depends(get_openai_api_user),
    db: AsyncSession = Depends(get_db),
):
    params = {
        "model": payload.model,
        "aspect_ratio": _aspect_from_size(payload.size, "1:1"),
        "num_outputs": payload.n,
        "extra": payload.extra,
    }
    task = await _create_openai_task(db, user, TaskType.image, payload.prompt, params, payload.n)
    await db.commit()
    async_result = generate_image.delay(task.id)
    task.celery_task_id = async_result.id
    await db.commit()
    return {
        "id": task.public_id,
        "object": "generation.task",
        "status": task.status.value,
        "model": payload.model,
        "task_url": f"/v1/tasks/{task.public_id}",
    }


@router.post("/videos/generations")
async def openai_video_generation(
    payload: OpenAIVideoRequest,
    user: User = Depends(get_openai_api_user),
    db: AsyncSession = Depends(get_db),
):
    params = {
        "model": payload.model,
        "aspect_ratio": _aspect_from_size(payload.size, "16:9"),
        "duration": payload.duration,
        "resolution": "VIDEO_RESOLUTION_1080P",
        "extra": payload.extra,
    }
    task = await _create_openai_task(db, user, TaskType.video, payload.prompt, params, 1)
    await db.commit()
    async_result = generate_video.delay(task.id)
    task.celery_task_id = async_result.id
    await db.commit()
    return {
        "id": task.public_id,
        "object": "generation.task",
        "status": task.status.value,
        "model": payload.model,
        "task_url": f"/v1/tasks/{task.public_id}",
    }


@router.get("/tasks/{public_id}", response_model=TaskDetailOut)
async def openai_get_task(
    public_id: str,
    user: User = Depends(get_openai_api_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.generation import GenerationTaskEvent

    task = await db.scalar(
        select(GenerationTask).where(GenerationTask.public_id == public_id, GenerationTask.user_id == user.id)
    )
    if not task:
        raise HTTPException(404, "Task not found")
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
