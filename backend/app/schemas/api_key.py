from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApiKeyStatus


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    user_id: int | None = None
    scopes: list[str] = Field(default_factory=lambda: ["image", "video", "models"])
    note: str | None = None
    expires_at: datetime | None = None


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    name: str
    prefix: str
    status: ApiKeyStatus
    scopes: list[str]
    note: str | None
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class ApiKeyCreatedOut(ApiKeyOut):
    key: str


class ApiKeyUpdate(BaseModel):
    name: str | None = None
    status: ApiKeyStatus | None = None
    scopes: list[str] | None = None
    note: str | None = None
    expires_at: datetime | None = None


class ApiKeyBatchDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
