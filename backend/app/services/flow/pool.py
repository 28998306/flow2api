"""账号池调度 + 并发闸门 + 账号刷新/冷却。

- 全局闸门:限制对 FLOW 的总并发(Redis 计数器)。
- 单账号闸门:限制每账号并发(账号同一 Profile 还需进程级互斥,见 worker)。
- 选号:跳过冷却/失效账号,按 (在用率 - 权重 - 余额) 排序优先低负载高余额。
- 冷却:配额耗尽长冷却、鉴权/限流短冷却。
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AccountStatus, AccountType
from app.models.flow_account import FlowAccount
from app.services.flow.client import FlowCredential, FlowError

GLOBAL_KEY = "flow:concurrency:global"
ACCOUNT_KEY = "flow:concurrency:account:{account_id}"

_sync_redis: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis


class NoAccountAvailable(FlowError):
    def __init__(self, message: str = "暂无可用账号或并发已满"):
        super().__init__(message, retryable=True, kind="transient")


def profile_path(account: FlowAccount) -> str:
    if os.path.isabs(account.chrome_profile):
        return account.chrome_profile
    return os.path.join(settings.FLOW_PROFILES_DIR, account.chrome_profile)


def build_credential(account: FlowAccount) -> FlowCredential:
    headers = {}
    if account.browser_headers:
        try:
            headers = json.loads(account.browser_headers)
        except (json.JSONDecodeError, TypeError):
            headers = {}
    return FlowCredential(
        account_id=account.id,
        label=account.label,
        bearer=account.bearer_token or "",
        project_id=account.project_id,
        session_id=account.session_id,
        session_token=account.session_token,
        google_cookies=account.google_cookies,
        proxy=resolve_proxy(account),
        browser_headers=headers,
    )


def resolve_proxy(account: FlowAccount) -> str | None:
    """账号专用代理优先,否则回退到全局 FLOW_PROXY。"""
    return (account.proxy or "").strip() or (settings.FLOW_PROXY or "").strip() or None


@contextmanager
def acquire_slot(db: Session, required_account_types: set[AccountType] | None = None):
    """选择账号并占用全局+账号并发槽位;退出时释放。yields (FlowAccount)。"""
    r = get_sync_redis()
    now = datetime.now(timezone.utc)

    global_count = r.incr(GLOBAL_KEY)
    if global_count == 1:
        r.expire(GLOBAL_KEY, 3600)
    if global_count > settings.FLOW_GLOBAL_CONCURRENCY:
        r.decr(GLOBAL_KEY)
        raise NoAccountAvailable("全局并发已满,请稍后重试")

    account: FlowAccount | None = None
    try:
        accounts = db.execute(
            select(FlowAccount).where(FlowAccount.status.in_([AccountStatus.active, AccountStatus.cooldown]))
        ).scalars().all()
        candidates = []
        for a in accounts:
            if required_account_types and a.account_type not in required_account_types:
                continue
            if a.status == AccountStatus.cooldown:
                if a.cooldown_until and a.cooldown_until > now:
                    continue
                a.status = AccountStatus.active
                a.cooldown_until = None
            candidates.append(a)
        if not candidates:
            raise NoAccountAvailable("没有可用账号")

        def score(a: FlowAccount) -> float:
            in_use = int(r.get(ACCOUNT_KEY.format(account_id=a.id)) or 0)
            load = in_use / max(1, a.max_concurrency)
            credits_bonus = -0.001 * (a.remaining_credits or 0)
            return load - (a.weight * 0.01) + credits_bonus

        candidates.sort(key=score)

        for a in candidates:
            akey = ACCOUNT_KEY.format(account_id=a.id)
            cnt = r.incr(akey)
            if cnt == 1:
                r.expire(akey, 3600)
            if cnt <= a.max_concurrency:
                account = a
                break
            r.decr(akey)

        if account is None:
            raise NoAccountAvailable("所有账号并发已满")

        account.last_used_at = now
        db.commit()
        yield account
    finally:
        r.decr(GLOBAL_KEY)
        if account is not None:
            r.decr(ACCOUNT_KEY.format(account_id=account.id))


def mark_success(db: Session, account: FlowAccount, remaining_credits: int | None = None) -> None:
    account.success_count += 1
    account.last_error = None
    if remaining_credits is not None:
        account.remaining_credits = remaining_credits
    db.commit()


def mark_failure(db: Session, account: FlowAccount, error: str, kind: str | None = None) -> None:
    account.fail_count += 1
    account.last_error = error[:1000]
    cooldown = 0
    if kind == "quota":
        cooldown = settings.FLOW_QUOTA_COOLDOWN
        account.remaining_credits = 0
    elif kind in ("auth", "recaptcha", "transient"):
        cooldown = settings.FLOW_AUTH_COOLDOWN
    if cooldown > 0:
        account.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown)
        account.status = AccountStatus.cooldown
    db.commit()


def update_bearer(db: Session, account: FlowAccount, bearer: str | None, headers: dict | None) -> None:
    if bearer and bearer.startswith("ya29."):
        account.bearer_token = bearer
        account.last_bearer_refresh = datetime.now(timezone.utc)
    if headers:
        account.browser_headers = json.dumps(headers, ensure_ascii=False)
    db.commit()


def account_lock_key(account_id: int) -> str:
    """同一 Chrome Profile 进程级互斥的 Redis 锁 key。"""
    return f"flow:profile_lock:{account_id}"
