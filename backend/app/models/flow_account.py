from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import AccountStatus, AccountType


class FlowAccount(Base):
    """FLOW 上游账号 = 一个登录了 labs.google 的 Google 账号。

    生成所需的 reCAPTCHA token 与 ya29 Bearer 都依赖该账号的持久化 Chrome Profile。
    """

    __tablename__ = "flow_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # __Secure-next-auth.session-token(ST,长期有效):用于 HTTP 换 ya29 AT
    session_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # .google.com/accounts.google.com cookies(JSON 或 "a=b; c=d"),用于纯 HTTP reCAPTCHA 提高评分
    google_cookies: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ya29 OAuth Bearer(AT,缓存值;由 ST 自动刷新)
    bearer_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 旧字段保留兼容;当前纯协议模式不使用 Chrome Profile
    chrome_profile: Mapped[str] = mapped_column(String(255), nullable=False)

    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 该账号专用代理(留空则用全局 FLOW_PROXY)。reCAPTCHA 与 HTTP 提交走同一出口 IP。
    proxy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False, length=20),
        default=AccountType.normal,
        nullable=False,
    )
    paygate_tier: Mapped[str | None] = mapped_column(String(40), nullable=True)
    remaining_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # HTTP 指纹头(JSON 字符串),用于 HTTP 提交对齐
    browser_headers: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, length=20),
        default=AccountStatus.active,
        nullable=False,
    )
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_bearer_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bearer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cookies_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_refresh_minutes: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
