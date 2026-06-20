from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import AccountStatus


class FlowAccount(Base):
    """FLOW 上游账号 = 一个登录了 labs.google 的 Google 账号。

    生成所需的 reCAPTCHA token 与 ya29 Bearer 都依赖该账号的持久化 Chrome Profile。
    """

    __tablename__ = "flow_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ya29 OAuth Bearer(会过期,由浏览器 oracle 刷新)
    bearer_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 持久化 Chrome Profile 目录名(相对 FLOW_PROFILES_DIR)
    chrome_profile: Mapped[str] = mapped_column(String(255), nullable=False)

    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paygate_tier: Mapped[str | None] = mapped_column(String(40), nullable=True)
    remaining_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 浏览器抓到的指纹头(JSON 字符串),用于 HTTP 提交对齐
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
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
