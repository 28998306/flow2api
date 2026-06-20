"""Google Flow (Labs FX) 真实协议常量与请求体构造。

来源:对 labs.google/fx/tools/flow 前端 chunk 的逆向(google_flow_protocol)。
- API base:aisandbox-pa.googleapis.com,工具名 PINHOLE
- 出视频:异步提交 + 轮询 + 媒体下载(base64)
- 出图:batchGenerateImages(Imagen,同步返回)
- 每次生成都需要新鲜的 reCAPTCHA Enterprise token
"""

from __future__ import annotations

import time
import uuid
from typing import Any

BASE_URL = "https://aisandbox-pa.googleapis.com"
API_KEY = "AIzaSyBtrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY"
TOOL = "PINHOLE"
RECAPTCHA_SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
FLOW_URL = "https://labs.google/fx/tools/flow"
RECAPTCHA_ENTERPRISE_JS = (
    "https://www.google.com/recaptcha/enterprise.js?render=" + RECAPTCHA_SITE_KEY
)

# reCAPTCHA action 名(出图/出视频不同)
ACTION_VIDEO = "VIDEO_GENERATION"
ACTION_IMAGE = "IMAGE_GENERATION"

# ---------------- 端点 ---------------- #
EP_VIDEO_TEXT = "/v1/video:batchAsyncGenerateVideoText"
EP_VIDEO_START_IMAGE = "/v1/video:batchAsyncGenerateVideoStartImage"
EP_VIDEO_CHECK = "/v1/video:batchCheckAsyncVideoGenerationStatus"
EP_IMAGE_GENERATE = "/v1/image:batchGenerateImages"  # 逆向确认函数名 batchGenerateImages
EP_MEDIA = "/v1/media/{name}"
EP_CREDITS = "/v1/credits"
EP_VIDEO_CREDIT_STATUS = "/v1/whisk:getVideoCreditStatus"

# ---------------- 模型映射(UI 名 -> 真实 model key) ---------------- #
VIDEO_MODEL_MAP = {
    "omni_flash": "abra_t2v_10s",
    "abra": "abra_t2v_10s",
    "veo_3_1_lite": "veo_3_1_lite",
    "veo_3_1_fast": "veo_3_1_fast",
    "veo_3_1_quality": "veo_3_1_quality",
}
DEFAULT_VIDEO_MODEL = "omni_flash"

IMAGE_MODEL_MAP = {
    "imagen_fast": "IMAGEN_3_5_FAST",
    "imagen": "IMAGEN_3_5",
    "imagen_3": "IMAGEN_3",
}
DEFAULT_IMAGE_MODEL = "imagen"

# ---------------- 比例映射(UI "16:9" -> 协议枚举) ---------------- #
VIDEO_ASPECT_MAP = {
    "16:9": "VIDEO_ASPECT_RATIO_LANDSCAPE",
    "9:16": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "1:1": "VIDEO_ASPECT_RATIO_SQUARE",
}
DEFAULT_VIDEO_ASPECT = "VIDEO_ASPECT_RATIO_LANDSCAPE"

IMAGE_ASPECT_MAP = {
    "1:1": "IMAGE_ASPECT_RATIO_SQUARE",
    "9:16": "IMAGE_ASPECT_RATIO_PORTRAIT",
    "16:9": "IMAGE_ASPECT_RATIO_LANDSCAPE",
    "3:4": "IMAGE_ASPECT_RATIO_PORTRAIT",
    "4:3": "IMAGE_ASPECT_RATIO_LANDSCAPE",
}
DEFAULT_IMAGE_ASPECT = "IMAGE_ASPECT_RATIO_SQUARE"

# 终态
TERMINAL_STATUSES = {
    "MEDIA_GENERATION_STATUS_SUCCESSFUL",
    "MEDIA_GENERATION_STATUS_FAILED",
    "MEDIA_GENERATION_STATUS_CANCELLED",
}
STATUS_SUCCESS = "MEDIA_GENERATION_STATUS_SUCCESSFUL"


def http_headers(bearer: str, browser_headers: dict[str, str] | None = None) -> dict[str, str]:
    """构造与浏览器一致的请求头(text/plain + labs.google Origin)。"""
    headers = {
        "Authorization": "Bearer " + bearer,
        "Content-Type": "text/plain;charset=UTF-8",
        "Origin": "https://labs.google",
        "Referer": "https://labs.google/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        ),
    }
    if browser_headers:
        # 复用浏览器抓到的 UA / sec-ch-ua / accept-language,指纹更一致
        for k, v in browser_headers.items():
            if k.lower() in (
                "user-agent",
                "accept-language",
                "sec-ch-ua",
                "sec-ch-ua-mobile",
                "sec-ch-ua-platform",
            ):
                headers[k] = v
    return headers


def _session_id(session_id: str | None) -> str:
    # 浏览器格式形如 ";1780933431865"
    return session_id or (";" + str(int(time.time() * 1000)))


def build_video_text_body(
    *,
    prompt: str,
    model: str,
    aspect: str,
    recaptcha_token: str,
    project_id: str | None = None,
    session_id: str | None = None,
    seed: int,
) -> dict[str, Any]:
    """文生视频请求体(对齐 captured_generate_request.json)。"""
    client_context: dict[str, Any] = {
        "tool": TOOL,
        "sessionId": _session_id(session_id),
        "recaptchaContext": {
            "token": recaptcha_token,
            "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB",
        },
    }
    if project_id:
        client_context["projectId"] = project_id

    return {
        "mediaGenerationContext": {
            "batchId": str(uuid.uuid4()),
            "audioFailurePreference": "BLOCK_SILENCED_VIDEOS",
        },
        "clientContext": client_context,
        "requests": [
            {
                "aspectRatio": VIDEO_ASPECT_MAP.get(aspect, aspect),
                "textInput": {"structuredPrompt": {"parts": [{"text": prompt}]}},
                "videoModelKey": VIDEO_MODEL_MAP.get(model, model),
                "seed": seed,
                "metadata": {},
            }
        ],
        "useV2ModelConfig": True,
    }


def build_image_body(
    *,
    prompt: str,
    model: str,
    aspect: str,
    recaptcha_token: str,
    project_id: str | None = None,
    session_id: str | None = None,
    seed: int,
    num_images: int = 1,
) -> dict[str, Any]:
    """文生图请求体(batchGenerateImages,Imagen)。

    注:image:batchGenerateImages 的字段以逆向 schema 为准,这里给出最可用的形态;
    若上游字段微调,只需改这里,不影响上层。
    """
    client_context: dict[str, Any] = {
        "tool": TOOL,
        "sessionId": _session_id(session_id),
        "recaptchaContext": {
            "token": recaptcha_token,
            "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB",
        },
    }
    if project_id:
        client_context["projectId"] = project_id

    return {
        "clientContext": client_context,
        "requests": [
            {
                "aspectRatio": IMAGE_ASPECT_MAP.get(aspect, aspect),
                "imageModelName": IMAGE_MODEL_MAP.get(model, model),
                "prompt": prompt,
                "structuredPrompt": {"parts": [{"text": prompt}]},
                "seed": seed,
                "imageInputs": [],
                "numberOfImages": num_images,
            }
        ],
    }


def media_url(name: str) -> str:
    from urllib.parse import quote

    return f"{BASE_URL}{EP_MEDIA.format(name=quote(name))}?key={API_KEY}&clientContext.tool={TOOL}"
