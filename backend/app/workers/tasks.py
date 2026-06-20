"""Celery 任务:出图 / 出视频(真实 Google Flow 协议)。

执行流程(对齐 google_flow_protocol 的账号池逻辑):
1. 取任务,标记 running。
2. 账号池选号 + 占用并发槽位。
3. 获取该账号 Chrome Profile 的进程级互斥锁(同一 Profile 不能被多浏览器同时打开)。
4. 浏览器 Oracle:打开 Profile,抓取新鲜 Bearer + reCAPTCHA token + 指纹头。
5. HTTP 提交生成;出视频再轮询 + 下载 base64;鉴权失效则刷新一次重试。
6. 结果转存对象存储,落库,推进度;失败则按 kind 冷却账号并退还额度。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from celery import shared_task

from app.core.config import settings
from app.core.db_sync import SyncSessionLocal
from app.models.enums import TaskStatus, TaskType
from app.models.generation import GenerationTask
from app.services.flow import protocol as P
from app.services.flow.client import FlowClient, FlowError
from app.services.flow.pool import (
    NoAccountAvailable,
    account_lock_key,
    acquire_slot,
    build_credential,
    get_sync_redis,
    mark_failure,
    mark_success,
    profile_path,
    update_bearer,
)
from app.services.flow.recaptcha import RecaptchaError, get_token_and_bearer
from app.services.progress import publish_progress
from app.services.storage import store_bytes, store_remote_asset

MAX_ACCOUNT_RETRIES = 3
PROFILE_LOCK_TTL = settings.FLOW_VIDEO_MAX_WAIT + 180


def _push(task: GenerationTask, status: TaskStatus, progress: int, error: str | None = None):
    publish_progress(
        task.public_id,
        {
            "public_id": task.public_id,
            "status": status.value,
            "progress": progress,
            "outputs": task.outputs,
            "error": error,
        },
    )


class _ProfileLock:
    """基于 Redis 的账号 Profile 互斥锁。"""

    def __init__(self, account_id: int):
        self.key = account_lock_key(account_id)
        self.r = get_sync_redis()
        self.acquired = False

    def __enter__(self):
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.r.set(self.key, "1", nx=True, ex=PROFILE_LOCK_TTL):
                self.acquired = True
                return self
            time.sleep(1)
        raise NoAccountAvailable("账号 Profile 正被占用")

    def __exit__(self, *exc):
        if self.acquired:
            self.r.delete(self.key)


def _store_outputs(outputs: list[dict], user_id: int) -> list[dict]:
    stored = []
    for out in outputs:
        if "bytes" in out:
            url = store_bytes(out["bytes"], out["type"], user_id, ext=out.get("ext"))
        else:
            url = store_remote_asset(out["url"], out["type"], user_id)
        stored.append({"url": url, "type": out["type"]})
    return stored


def _attempt_once(db, task: GenerationTask, task_type: TaskType) -> bool:
    with acquire_slot(db) as account:
        task.account_id = account.id
        db.commit()

        action = P.ACTION_IMAGE if task_type == TaskType.image else P.ACTION_VIDEO

        with _ProfileLock(account.id):
            # 1) 浏览器 oracle:拿 recaptcha + 刷新 bearer + 指纹头
            try:
                oracle = get_token_and_bearer(profile_path(account), action=action)
            except RecaptchaError as exc:
                mark_failure(db, account, str(exc), kind="recaptcha")
                raise FlowError(str(exc), retryable=True, kind="recaptcha") from exc
            update_bearer(db, account, oracle.bearer, oracle.browser_headers)

            cred = build_credential(account)
            if not cred.bearer:
                mark_failure(db, account, "无可用 Bearer", kind="auth")
                raise FlowError("账号无 Bearer,需先在浏览器登录该 Profile", retryable=True, kind="auth")

            client = FlowClient(
                cred,
                use_curl=settings.FLOW_USE_CURL,
                impersonate=settings.FLOW_IMPERSONATE,
            )

            def progress_cb(p: int):
                task.progress = p
                db.commit()
                _push(task, TaskStatus.running, p)

            # 2) 提交生成(鉴权失效则刷新 oracle 一次重试)
            for sub_attempt in range(2):
                try:
                    if task_type == TaskType.image:
                        progress_cb(40)
                        result = client.submit_image(task.prompt, task.params, oracle.recaptcha_token)
                    else:
                        result = client.submit_video(
                            task.prompt, task.params, oracle.recaptcha_token, progress_cb
                        )
                    break
                except FlowError as exc:
                    if exc.kind == "auth" and sub_attempt == 0:
                        oracle = get_token_and_bearer(profile_path(account), action=action)
                        update_bearer(db, account, oracle.bearer, oracle.browser_headers)
                        client = FlowClient(build_credential(account), use_curl=settings.FLOW_USE_CURL)
                        continue
                    mark_failure(db, account, str(exc), kind=exc.kind)
                    raise

            # 3) 转存对象存储
            progress_cb(96)
            stored = _store_outputs(result.outputs, task.user_id)

            task.outputs = stored
            task.status = TaskStatus.succeeded
            task.progress = 100
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
            mark_success(db, account, remaining_credits=result.remaining_credits)
            _push(task, TaskStatus.succeeded, 100)
            return True


def _run_generation(task_id: int, task_type: TaskType) -> None:
    db = SyncSessionLocal()
    try:
        task = db.get(GenerationTask, task_id)
        if task is None or task.status == TaskStatus.cancelled:
            return

        task.status = TaskStatus.running
        task.started_at = datetime.now(timezone.utc)
        task.progress = 5
        db.commit()
        _push(task, TaskStatus.running, 5)

        last_error: str | None = None
        for _attempt in range(MAX_ACCOUNT_RETRIES):
            try:
                if _attempt_once(db, task, task_type):
                    return
            except NoAccountAvailable as exc:
                last_error = str(exc)
                time.sleep(2)
                continue
            except FlowError as exc:
                last_error = str(exc)
                if not exc.retryable:
                    break
                continue

        task.status = TaskStatus.failed
        task.error = last_error or "生成失败"
        task.finished_at = datetime.now(timezone.utc)
        db.commit()
        _push(task, TaskStatus.failed, task.progress, error=task.error)
        _refund(task)
    finally:
        db.close()


def _refund(task: GenerationTask) -> None:
    r = get_sync_redis()
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"quota:daily:{task.user_id}:{task.type.value}:{date}"
    try:
        r.decr(key)
    except Exception:  # noqa: BLE001
        pass


@shared_task(name="tasks.generate_image", bind=True, max_retries=0)
def generate_image(self, task_id: int) -> None:
    _run_generation(task_id, TaskType.image)


@shared_task(name="tasks.generate_video", bind=True, max_retries=0)
def generate_video(self, task_id: int) -> None:
    _run_generation(task_id, TaskType.video)
