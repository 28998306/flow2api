from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskStatus, TaskType


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str | None = None
    model: str = "nano_banana"
    aspect_ratio: str = "1:1"
    resolution: str | None = None
    num_outputs: int = Field(default=1, ge=1, le=4)
    seed: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    model: str = "omni_flash"
    duration: int = Field(default=5, ge=2, le=20)
    aspect_ratio: str = "16:9"
    resolution: str = "VIDEO_RESOLUTION_1080P"
    image_url: str | None = None  # 图生视频可选首帧
    seed: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    type: TaskType
    status: TaskStatus
    progress: int
    prompt: str
    params: dict[str, Any]
    outputs: list[dict[str, Any]]
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class TaskEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    stage: str
    message: str
    progress: int | None
    account_id: int | None
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    meta: dict[str, Any]
    created_at: datetime


class TaskDetailOut(TaskOut):
    account_id: int | None = None
    celery_task_id: str | None = None
    started_at: datetime | None = None
    events: list[TaskEventOut] = Field(default_factory=list)


class TaskCreatedOut(BaseModel):
    public_id: str
    status: TaskStatus
    type: TaskType


class TaskListOut(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class BatchIdsIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class BatchPublicIdsIn(BaseModel):
    public_ids: list[str] = Field(min_length=1, max_length=500)


class ModelOut(BaseModel):
    id: str
    object: str = "model"
    type: TaskType
    label: str
    provider: str = "google-flow"
    account_types: list[str]
    supports_4k: bool = False
    supports_image_input: bool = False
    description: str | None = None


class ModelListOut(BaseModel):
    object: str = "list"
    data: list[ModelOut]
