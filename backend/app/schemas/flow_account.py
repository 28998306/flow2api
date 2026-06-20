from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AccountStatus, AccountType


class FlowAccountCreate(BaseModel):
    label: str
    session_token: str  # __Secure-next-auth.session-token(ST),核心凭证
    google_cookies: str | None = None  # Google cookies(JSON 或 cookie header),用于纯 HTTP reCAPTCHA 提分
    project_id: str  # 出图为项目作用域,必填
    chrome_profile: str | None = None  # 留空则用 label 自动生成
    email: str | None = None
    session_id: str | None = None
    proxy: str | None = None  # 留空则用全局 FLOW_PROXY
    account_type: AccountType = AccountType.normal
    cookies_expires_at: datetime | None = None
    auto_refresh_minutes: int = Field(default=50, ge=5, le=1440)
    weight: int = 1
    max_concurrency: int = 2


class FlowAccountUpdate(BaseModel):
    label: str | None = None
    email: str | None = None
    session_token: str | None = None
    google_cookies: str | None = None
    chrome_profile: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    proxy: str | None = None
    account_type: AccountType | None = None
    cookies_expires_at: datetime | None = None
    auto_refresh_minutes: int | None = Field(default=None, ge=5, le=1440)
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
    proxy: str | None
    account_type: AccountType
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
    bearer_expires_at: datetime | None = None
    cookies_expires_at: datetime | None = None
    next_refresh_at: datetime | None = None
    auto_refresh_minutes: int = 50
    has_bearer: bool = False
    has_session_token: bool = False
    has_google_cookies: bool = False
    created_at: datetime

    @classmethod
    def from_account(cls, a) -> "FlowAccountOut":
        data = cls.model_validate(a)
        data.has_bearer = bool(getattr(a, "bearer_token", None))
        data.has_session_token = bool(getattr(a, "session_token", None))
        data.has_google_cookies = bool(getattr(a, "google_cookies", None))
        return data


class FlowAccountImportOut(BaseModel):
    created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class FlowAccountBatchImport(BaseModel):
    accounts: list[FlowAccountCreate] = Field(min_length=1, max_length=200)


class FlowAccountBatchDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class FlowAccountBatchUpdate(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    status: AccountStatus | None = None
    account_type: AccountType | None = None
    proxy: str | None = None
    max_concurrency: int | None = Field(default=None, ge=1, le=20)
