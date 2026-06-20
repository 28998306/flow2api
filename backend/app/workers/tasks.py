"""Celery 任务:出图 / 出视频(真实 Google Flow 协议,已实测跑通)。

执行流程(ST + 纯 HTTP reCAPTCHA 模型):
1. 取任务,标记 running。
2. 账号池选号 + 占用并发槽位。
3. token_manager:用账号 ST 纯 HTTP 换/刷新 ya29 AT(带缓存)。
4. reCAPTCHA Enterprise anchor/reload 纯 HTTP 协议获取 recaptcha token。
5. HTTP 提交生成(application/json + chrome124 指纹);鉴权失效则强制刷新 AT + 重取 token 重试一次。
6. 结果转存对象存储(出图为 fifeUrl 直链),落库,推进度;失败按 kind 冷却账号并退还额度。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from celery import shared_task

from app.core.config import settings
from app.core.db_sync import SyncSessionLocal
from app.models.enums import AccountType, TaskStatus, TaskType
from app.models.generation import GenerationTask
from app.services.flow import protocol as P
from app.services.flow import token_manager
from app.services.flow.client import FlowClient, FlowError
from app.services.flow.pool import (
    NoAccountAvailable,
    acquire_slot,
    build_credential,
    get_sync_redis,
    mark_failure,
    mark_success,
    profile_path,
    resolve_proxy,
    update_bearer,
)
from app.services.flow.recaptcha import RecaptchaError, get_recaptcha_token
from app.services.progress import publish_progress
from app.services.storage import store_bytes, store_remote_asset
from app.services.task_events import log_task_event

MAX_ACCOUNT_RETRIES = 3


def _required_account_types(task: GenerationTask, task_type: TaskType) -> set[AccountType] | None:
    model = str(task.params.get("model") or "").lower()
    resolution = str(task.params.get("resolution") or "").lower()
    if task_type == TaskType.image and ("4k" in model or "4k" in resolution):
        return {AccountType.ula}
    if model in {"banana_pro", "imagen", "veo_3_1_fast", "veo_3_1_quality"}:
        return {AccountType.pro, AccountType.ula}
    return None


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


def _event(
    db,
    task: GenerationTask,
    stage: str,
    message: str,
    *,
    level: str = "info",
    progress: int | None = None,
    request: dict | None = None,
    response: dict | None = None,
    meta: dict | None = None,
):
    log_task_event(
        db,
        task,
        stage,
        message,
        level=level,
        progress=progress,
        account_id=task.account_id,
        request=request,
        response=response,
        meta=meta,
    )


def _store_outputs(outputs: list[dict], user_id: int, proxy: str | None = None) -> list[dict]:
    stored = []
    for out in outputs:
        if "bytes" in out:
            url = store_bytes(out["bytes"], out["type"], user_id, ext=out.get("ext"))
        else:
            try:
                url = store_remote_asset(out["url"], out["type"], user_id, proxy=proxy)
            except Exception:  # noqa: BLE001
                # If local object storage is unreachable, do not lose a successful Flow generation.
                # Flow image URLs are signed but immediately usable by the frontend.
                url = out["url"]
        stored.append({"url": url, "type": out["type"]})
    return stored


def _refresh_at(db, account, *, force: bool = False) -> str:
    """用账号 ST 换/刷新 ya29 AT,并把缓存写回账号。返回 AT。"""
    if not account.session_token:
        mark_failure(db, account, "账号缺少 session_token(ST)", kind="auth")
        raise FlowError("账号缺少 session_token(ST),请在后台填入", retryable=False, kind="auth")
    try:
        tok = token_manager.get_access_token(
            account.session_token,
            force=force,
            impersonate=settings.FLOW_IMPERSONATE,
            proxy=resolve_proxy(account),
        )
    except token_manager.TokenError as exc:
        mark_failure(db, account, str(exc), kind=exc.kind)
        raise FlowError(str(exc), retryable=(exc.kind != "auth"), kind=exc.kind) from exc
    if tok.email and not account.email:
        account.email = tok.email
    account.bearer_expires_at = datetime.fromtimestamp(tok.expires_at, tz=timezone.utc)
    account.next_refresh_at = datetime.fromtimestamp(
        max(0, tok.expires_at - account.auto_refresh_minutes * 60), tz=timezone.utc
    )
    update_bearer(db, account, tok.token, None)
    return tok.token


def _attempt_once(db, task: GenerationTask, task_type: TaskType) -> bool:
    with acquire_slot(db, required_account_types=_required_account_types(task, task_type)) as account:
        task.account_id = account.id
        _event(
            db,
            task,
            "account_acquired",
            f"已选择账号 {account.label}",
            progress=10,
            meta={"account_type": getattr(account.account_type, "value", str(account.account_type))},
        )
        db.commit()

        action = P.ACTION_IMAGE if task_type == TaskType.image else P.ACTION_VIDEO
        proxy = resolve_proxy(account)

        # 1) 刷新 AT(纯 HTTP,带缓存)
        _event(db, task, "token_refresh", "开始刷新/校验 Labs access token", progress=20)
        bearer = _refresh_at(db, account)
        _event(db, task, "token_refresh", "Labs access token 已就绪", progress=25)

        def build_client(b: str) -> FlowClient:
            cred = build_credential(account)
            cred.bearer = b
            return FlowClient(cred, use_curl=settings.FLOW_USE_CURL, impersonate=settings.FLOW_IMPERSONATE)

        def progress_cb(p: int):
            task.progress = p
            db.commit()
            _push(task, TaskStatus.running, p)

        # 2) reCAPTCHA 分数仍可能波动:每次失败都重新走纯 HTTP anchor/reload 取新 token,
        #    重试期间不冷却账号(只在彻底耗尽后才冷却)。鉴权失效则强刷一次 AT。
        result = None
        last_exc: FlowError | None = None
        auth_refreshed = False
        retries = max(1, settings.FLOW_RECAPTCHA_RETRIES)
        for attempt in range(retries):
            progress_cb(30)
            _event(
                db,
                task,
                "recaptcha",
                f"开始获取 reCAPTCHA token({attempt + 1}/{retries})",
                progress=30,
                meta={"action": action},
            )
            try:
                oracle = get_recaptcha_token(
                    profile_path(account),
                    session_token=account.session_token,
                        google_cookies=account.google_cookies,
                    project_id=account.project_id,
                    proxy=proxy,
                    action=action,
                )
            except RecaptchaError as exc:
                _event(db, task, "recaptcha", str(exc), level="warn", progress=30)
                last_exc = FlowError(str(exc), retryable=True, kind="recaptcha")
                time.sleep(settings.FLOW_RECAPTCHA_RETRY_DELAY)
                continue

            client = build_client(bearer)
            try:
                if task_type == TaskType.image:
                    progress_cb(60)
                    _event(
                        db,
                        task,
                        "flow_submit",
                        "提交 Flow 出图请求",
                        progress=60,
                        request={"prompt": task.prompt, "params": task.params},
                    )
                    result = client.submit_image(task.prompt, task.params, oracle.recaptcha_token)
                else:
                    _event(
                        db,
                        task,
                        "flow_submit",
                        "提交 Flow 出视频请求并开始轮询",
                        progress=35,
                        request={"prompt": task.prompt, "params": task.params},
                    )
                    result = client.submit_video(
                        task.prompt, task.params, oracle.recaptcha_token, progress_cb
                    )
                _event(
                    db,
                    task,
                    "flow_result",
                    "Flow 生成成功",
                    progress=95,
                    response={"output_count": len(result.outputs), "remaining_credits": result.remaining_credits},
                )
                break
            except FlowError as exc:
                _event(db, task, "flow_error", str(exc), level="warn", progress=task.progress)
                last_exc = exc
                if exc.kind == "recaptcha":
                    time.sleep(settings.FLOW_RECAPTCHA_RETRY_DELAY)
                    continue
                if exc.kind == "auth" and not auth_refreshed:
                    auth_refreshed = True
                    bearer = _refresh_at(db, account, force=True)
                    continue
                # quota / 其它不可重试错误:冷却并抛出
                mark_failure(db, account, str(exc), kind=exc.kind)
                raise

        if result is None:
            msg = str(last_exc) if last_exc else "生成失败(无结果)"
            kind = last_exc.kind if last_exc else "transient"
            mark_failure(db, account, msg, kind=kind)
            raise FlowError(msg, retryable=True, kind=kind)

        # 3) 转存对象存储(出图为 fifeUrl 签名直链)
        progress_cb(96)
        _event(db, task, "storage", "开始转存生成结果", progress=96)
        stored = _store_outputs(result.outputs, task.user_id, proxy=proxy)

        task.outputs = stored
        task.status = TaskStatus.succeeded
        task.progress = 100
        task.finished_at = datetime.now(timezone.utc)
        db.commit()
        mark_success(db, account, remaining_credits=result.remaining_credits)
        _event(db, task, "completed", "任务完成", progress=100, response={"outputs": stored})
        db.commit()
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
        _event(db, task, "started", "任务开始执行", progress=5)
        db.commit()
        _push(task, TaskStatus.running, 5)

        last_error: str | None = None
        for _attempt in range(MAX_ACCOUNT_RETRIES):
            try:
                if _attempt_once(db, task, task_type):
                    return
            except NoAccountAvailable as exc:
                if not last_error:
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
        _event(db, task, "failed", task.error, level="error", progress=task.progress)
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
