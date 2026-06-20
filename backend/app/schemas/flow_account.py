from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccountStatus


class FlowAccountCreate(BaseModel):
    label: str
    chrome_profile: str  # 持久化 Chrome Profile 目录名(相对 FLOW_PROFILES_DIR)
    email: str | None = None
    bearer_token: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    weight: int = 1
    max_concurrency: int = 2


class FlowAccountUpdate(BaseModel):
    label: str | None = None
    email: str | None = None
    bearer_token: str | None = None
    chrome_profile: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    status: AccountStatus | None = None
    weight: int | None = None
    max_concurrency: int | None = None


class FlowAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    email: str | None
    chrome_profile: str
    project_id: str | None
    paygate_tier: str | None
    remaining_credits: int | None
    status: AccountStatus
    weight: int
    max_concurrency: int
    success_count: int
    fail_count: int
    last_error: str | None
    last_used_at: datetime | None
    last_bearer_refresh: datetime | None
    has_bearer: bool = False
    created_at: datetime

    @classmethod
    def from_account(cls, a) -> "FlowAccountOut":
        data = cls.model_validate(a)
        data.has_bearer = bool(getattr(a, "bearer_token", None))
        return data
