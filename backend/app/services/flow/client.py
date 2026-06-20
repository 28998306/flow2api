"""FLOW HTTP 客户端(真实 Google Flow 协议)。

封装出图 / 出视频的提交、轮询、下载,以及错误分类(鉴权失效 / 可重试 / 配额耗尽)。
默认用 httpx;若安装了 curl_cffi,可用 Chrome TLS 指纹模拟以降低风控概率。

注意:出视频是「异步提交 -> 轮询状态 -> 下载 base64」;出图是「同步返回」。
每次生成都需要外部传入新鲜的 recaptcha_token(由 recaptcha.py 的浏览器 oracle 产出)。
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.core.config import settings
from app.services.flow import protocol as P

try:  # 可选:Chrome TLS 指纹
    from curl_cffi import requests as _curl_requests  # type: ignore
except Exception:  # noqa: BLE001
    _curl_requests = None


class FlowError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        status_code: int | None = None,
        kind: str | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.kind = kind  # "auth" | "quota" | "recaptcha" | "transient" | None


@dataclass
class FlowCredential:
    account_id: int
    label: str
    bearer: str
    project_id: str | None = None
    session_id: str | None = None
    browser_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FlowResult:
    outputs: list[dict[str, Any]]
    raw: dict[str, Any] = field(default_factory=dict)
    remaining_credits: int | None = None


# ----------------------------- 错误分类 ----------------------------- #
def _is_auth_error(status: int, text: str) -> bool:
    if status == 401:
        return True
    low = text.lower()
    needles = ["unauthenticated", "invalid credentials", "invalid authentication", "access_token"]
    return status == 403 and any(n in low for n in needles)


def _is_quota_exhausted(status: int, text: str) -> bool:
    low = text.lower()
    return status == 429 and ("user_quota_reached" in low or "public_error_user_quota_reached" in low)


def _is_recaptcha_error(status: int, text: str) -> bool:
    low = text.lower()
    return status == 403 and ("recaptcha evaluation failed" in low or "public_error_unusual_activity" in low)


def _classify(status: int, body: Any) -> FlowError | None:
    if status == 200:
        return None
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    if _is_quota_exhausted(status, text):
        return FlowError("账号配额已耗尽", retryable=False, status_code=429, kind="quota")
    if _is_auth_error(status, text):
        return FlowError("账号鉴权失效", retryable=True, status_code=status, kind="auth")
    if _is_recaptcha_error(status, text):
        return FlowError("reCAPTCHA 校验失败", retryable=True, status_code=403, kind="recaptcha")
    if status in (429, 500, 502, 503, 504):
        return FlowError(f"上游暂时不可用 {status}", retryable=True, status_code=status, kind="transient")
    return FlowError(f"请求被拒绝 {status}: {text[:300]}", retryable=False, status_code=status)


class FlowClient:
    def __init__(self, credential: FlowCredential, use_curl: bool | None = None, impersonate: str = "chrome136"):
        self.cred = credential
        self.use_curl = (_curl_requests is not None) if use_curl is None else (use_curl and _curl_requests is not None)
        self.impersonate = impersonate

    # ----------------------------- 出图 ----------------------------- #
    def submit_image(self, prompt: str, params: dict[str, Any], recaptcha_token: str) -> FlowResult:
        body = P.build_image_body(
            prompt=prompt,
            model=params.get("model", P.DEFAULT_IMAGE_MODEL),
            aspect=params.get("aspect_ratio", "1:1"),
            recaptcha_token=recaptcha_token,
            project_id=self.cred.project_id,
            session_id=self.cred.session_id,
            seed=params.get("seed") or 0,
            num_images=params.get("num_outputs", 1),
        )
        status, data = self._request("POST", P.EP_IMAGE_GENERATE, body)
        err = _classify(status, data)
        if err:
            raise err
        outputs = self._extract_image_outputs(data)
        return FlowResult(outputs=outputs, raw=data, remaining_credits=_credits(data))

    # ----------------------------- 出视频 ----------------------------- #
    def submit_video(
        self,
        prompt: str,
        params: dict[str, Any],
        recaptcha_token: str,
        progress_cb: Callable[[int], None] | None = None,
    ) -> FlowResult:
        body = P.build_video_text_body(
            prompt=prompt,
            model=params.get("model", P.DEFAULT_VIDEO_MODEL),
            aspect=params.get("aspect_ratio", "16:9"),
            recaptcha_token=recaptcha_token,
            project_id=self.cred.project_id,
            session_id=self.cred.session_id,
            seed=params.get("seed") or 0,
        )
        status, gen = self._request("POST", P.EP_VIDEO_TEXT, body)
        err = _classify(status, gen)
        if err:
            raise err

        media_name, project_id, _ = self._extract_media_ref(gen)
        if not media_name:
            raise FlowError("提交成功但未返回 media", retryable=True)
        if progress_cb:
            progress_cb(20)

        # 轮询
        check_body = {"media": [{"name": media_name, "projectId": project_id}]}
        waited = 0
        interval = settings.FLOW_VIDEO_POLL_INTERVAL
        final: dict[str, Any] | None = None
        while waited < settings.FLOW_VIDEO_MAX_WAIT:
            import time

            time.sleep(interval)
            waited += interval
            st, obj = self._request("POST", P.EP_VIDEO_CHECK, check_body)
            err = _classify(st, obj)
            if err and err.kind == "auth":
                raise err  # bearer 过期,交给上层刷新
            mstatus = _media_status(obj)
            if progress_cb:
                progress_cb(min(95, 25 + int(waited / max(1, settings.FLOW_VIDEO_MAX_WAIT) * 70)))
            if mstatus in P.TERMINAL_STATUSES:
                final = obj
                break

        if not final or _media_status(final) != P.STATUS_SUCCESS:
            raise FlowError(f"出视频未成功: {_media_status(final or {})}", retryable=True)

        # 下载 mp4 字节(返回给上层转存对象存储)
        if progress_cb:
            progress_cb(96)
        video_bytes = self._download_media_bytes(media_name)
        return FlowResult(
            outputs=[{"type": "video", "bytes": video_bytes, "ext": "mp4"}],
            raw=final,
            remaining_credits=_credits(final),
        )

    # ----------------------------- 媒体下载 ----------------------------- #
    def _download_media_bytes(self, media_name: str) -> bytes:
        status, obj = self._request_url("GET", P.media_url(media_name), None, timeout=180)
        err = _classify(status, obj)
        if err:
            raise err
        b64 = ((obj.get("video") or {}).get("encodedVideo") or "").strip() if isinstance(obj, dict) else ""
        if not b64:
            raise FlowError("media 响应无 encodedVideo", retryable=True)
        return base64.b64decode(b64)

    # ----------------------------- 底层 HTTP ----------------------------- #
    def _request(self, method: str, path: str, body: dict | None, timeout: int | None = None):
        return self._request_url(method, f"{P.BASE_URL}{path}", body, timeout)

    def _request_url(self, method: str, url: str, body: dict | None, timeout: int | None = None):
        timeout = timeout or settings.FLOW_REQUEST_TIMEOUT
        headers = P.http_headers(self.cred.bearer, self.cred.browser_headers)
        data = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        try:
            if self.use_curl:
                s = _curl_requests.Session(impersonate=self.impersonate)
                r = s.request(method, url, data=data, headers=headers, timeout=timeout)
                text = r.text
                status = r.status_code
            else:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    r = client.request(method, url, content=data, headers=headers)
                    text = r.text
                    status = r.status_code
        except Exception as exc:  # noqa: BLE001
            raise FlowError(f"网络错误: {exc}", retryable=True, kind="transient") from exc

        try:
            return status, (json.loads(text) if text else {})
        except json.JSONDecodeError:
            return status, text

    # ----------------------------- 解析 ----------------------------- #
    @staticmethod
    def _extract_media_ref(gen: Any) -> tuple[str | None, str | None, str | None]:
        media = (gen or {}).get("media") or [] if isinstance(gen, dict) else []
        if not media:
            return None, None, None
        m = media[0]
        return m.get("name"), m.get("projectId"), m.get("workflowId")

    @staticmethod
    def _extract_image_outputs(data: Any) -> list[dict[str, Any]]:
        if not isinstance(data, dict):
            raise FlowError("出图响应解析失败", retryable=True)
        outputs: list[dict[str, Any]] = []
        # 兼容多种可能结构:images[].encodedImage / media[].image.encodedImage / url
        for key in ("images", "generatedImages", "media", "results"):
            for item in data.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                b64 = (
                    item.get("encodedImage")
                    or (item.get("image") or {}).get("encodedImage")
                    or item.get("imageBytes")
                )
                if b64:
                    outputs.append({"type": "image", "bytes": base64.b64decode(b64), "ext": "png"})
                    continue
                url = item.get("url") or item.get("imageUrl") or (item.get("image") or {}).get("url")
                if url:
                    outputs.append({"type": "image", "url": url})
        if not outputs:
            raise FlowError("出图未返回图像数据", retryable=True)
        return outputs


def _media_status(obj: Any) -> str:
    try:
        return obj["media"][0]["mediaMetadata"]["mediaStatus"]["mediaGenerationStatus"]
    except Exception:  # noqa: BLE001
        return ""


def _credits(obj: Any) -> int | None:
    if isinstance(obj, dict) and isinstance(obj.get("remainingCredits"), (int, float)):
        return int(obj["remainingCredits"])
    return None
