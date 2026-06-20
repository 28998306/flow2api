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
API_BASE = BASE_URL + "/v1"
API_KEY = "AIzaSyBtrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY"
TOOL = "PINHOLE"
RECAPTCHA_SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
FLOW_URL = "https://labs.google/fx/tools/flow"
# ST -> AT(access token)交换端点;用 __Secure-next-auth.session-token cookie GET
AUTH_SESSION_URL = "https://labs.google/fx/api/auth/session"
SESSION_COOKIE_NAME = "__Secure-next-auth.session-token"
LABS_COOKIE_DOMAIN = "labs.google"
RECAPTCHA_ENTERPRISE_JS = (
    "https://www.google.com/recaptcha/enterprise.js?render=" + RECAPTCHA_SITE_KEY
)

# reCAPTCHA action 名(出图/出视频不同)
ACTION_VIDEO = "VIDEO_GENERATION"
ACTION_IMAGE = "IMAGE_GENERATION"

# ---------------- 端点 ---------------- #
EP_VIDEO_TEXT = "/v1/video:batchAsyncGenerateVideoText"
EP_VIDEO_START_IMAGE = "/v1/video:batchAsyncGenerateVideoStartImage"
EP_VIDEO_UPSAMPLE = "/v1/video:batchAsyncGenerateVideoUpsampleVideo"
EP_VIDEO_CHECK = "/v1/video:batchCheckAsyncVideoGenerationStatus"
# 出图为项目作用域:/v1/projects/{projectId}/flowMedia:batchGenerateImages
EP_IMAGE_GENERATE_TMPL = "/v1/projects/{project_id}/flowMedia:batchGenerateImages"
EP_MEDIA = "/v1/media/{name}"


def image_generate_path(project_id: str) -> str:
    return EP_IMAGE_GENERATE_TMPL.format(project_id=project_id)


# ---------------- 模型映射(UI 名 -> 真实 imageModelName) ---------------- #
# 真实可用值:NARWHAL(Gemini 3.1 flash image / nano-banana)、
#           GEM_PIX_2(Gemini 3.0 pro image / banana pro)、IMAGEN_3_5(Imagen 4)
VIDEO_MODEL_MAP = {
    "omni_flash": "abra_t2v_10s",
    "abra": "abra_t2v_10s",
    "veo_3_1_fast": "veo_3_1_t2v_fast_landscape",
    "veo_3_1_lite": "veo_3_1_t2v_lite_landscape",
    "veo_3_1_quality": "veo_3_1_t2v_landscape",
}
DEFAULT_VIDEO_MODEL = "omni_flash"
DEFAULT_VIDEO_UPSAMPLE_MODEL = "veo_3_1_upsampler_1080p"

IMAGE_MODEL_MAP = {
    "nano_banana": "NARWHAL",
    "banana": "NARWHAL",
    "flash": "NARWHAL",
    "banana_pro": "GEM_PIX_2",
    "pro": "GEM_PIX_2",
    "gemini_pro": "GEM_PIX_2",
    "imagen": "IMAGEN_3_5",
    "imagen_4k": "IMAGEN_3_5",
}
DEFAULT_IMAGE_MODEL = "nano_banana"

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
    """构造与浏览器一致的请求头(text/plain JSON payload + labs.google Origin)。"""
    headers = {
        "Authorization": "Bearer " + bearer,
        # Labs 前端用 text/plain 发送 JSON,避免 CORS 预检;reCAPTCHA 评估也会参考请求指纹。
        "Content-Type": "text/plain;charset=UTF-8",
        "Origin": "https://labs.google",
        "Referer": "https://labs.google/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if browser_headers:
        # 复用浏览器抓到的 UA / sec-ch-ua / accept-language,指纹更一致。
        # 注意:必须按规范化 key 覆盖,避免出现重复的 User-Agent/user-agent 双头(强 bot 信号 -> reCAPTCHA 直接判失败)。
        canonical = {
            "user-agent": "User-Agent",
            "accept-language": "Accept-Language",
            "sec-ch-ua": "sec-ch-ua",
            "sec-ch-ua-mobile": "sec-ch-ua-mobile",
            "sec-ch-ua-platform": "sec-ch-ua-platform",
        }
        for k, v in browser_headers.items():
            ck = canonical.get(k.lower())
            if ck and v:
                headers[ck] = v
    return headers


def _session_id(session_id: str | None) -> str:
    # 浏览器格式形如 ";1780933431865"
    return session_id or (";" + str(int(time.time() * 1000)))


def _client_context(recaptcha_token: str, project_id: str | None, session_id: str | None) -> dict[str, Any]:
    cc: dict[str, Any] = {
        "recaptchaContext": {
            "token": recaptcha_token,
            "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB",
        },
        "sessionId": _session_id(session_id),
        "tool": TOOL,
    }
    if project_id:
        cc["projectId"] = project_id
    return cc


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
    """文生视频请求体(对齐真实 batchAsyncGenerateVideoText)。"""
    cc = _client_context(recaptcha_token, project_id, session_id)
    cc["userPaygateTier"] = "PAYGATE_TIER_ONE"
    request_data = {
        "aspectRatio": VIDEO_ASPECT_MAP.get(aspect, aspect),
        "seed": seed,
        "textInput": {"prompt": prompt, "structuredPrompt": {"parts": [{"text": prompt}]}},
        "videoModelKey": VIDEO_MODEL_MAP.get(model, model),
        "metadata": {"sceneId": str(uuid.uuid4())},
    }
    return {
        "clientContext": cc,
        "requests": [request_data],
        "mediaGenerationContext": {"batchId": str(uuid.uuid4())},
        "useV2ModelConfig": True,
    }


def build_video_upsample_body(
    *,
    media_id: str,
    aspect: str,
    recaptcha_token: str,
    project_id: str,
    session_id: str | None = None,
    seed: int,
    resolution: str = "VIDEO_RESOLUTION_1080P",
    model: str = DEFAULT_VIDEO_UPSAMPLE_MODEL,
) -> dict[str, Any]:
    """视频放大请求体: 720P 生成结果 -> 1080P/4K media。"""
    cc = _client_context(recaptcha_token, project_id, session_id)
    request_data = {
        "aspectRatio": VIDEO_ASPECT_MAP.get(aspect, aspect),
        "resolution": resolution,
        "seed": seed,
        "videoInput": {"mediaId": media_id},
        "videoModelKey": model,
        "metadata": {"sceneId": str(uuid.uuid4())},
    }
    return {
        "clientContext": cc,
        "requests": [request_data],
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
    """文生图请求体(projects/{pid}/flowMedia:batchGenerateImages,已实测 200)。

    结构要点:clientContext 在外层和每个 request 内都要带;提示词用 structuredPrompt;
    顶层带 useNewMedia=true 与 mediaGenerationContext.batchId。
    """
    cc = _client_context(recaptcha_token, project_id, session_id)
    request_data = {
        "clientContext": cc,
        "seed": seed or 0,
        "imageModelName": IMAGE_MODEL_MAP.get(model, model),
        "imageAspectRatio": IMAGE_ASPECT_MAP.get(aspect, aspect),
        "structuredPrompt": {"parts": [{"text": prompt}]},
        "imageInputs": [],
    }
    return {
        "clientContext": cc,
        "mediaGenerationContext": {"batchId": str(uuid.uuid4())},
        "useNewMedia": True,
        "requests": [request_data],
    }


def media_url(name: str) -> str:
    from urllib.parse import quote

    return f"{BASE_URL}{EP_MEDIA.format(name=quote(name, safe=''))}?key={API_KEY}&clientContext.tool={TOOL}"


def labs_media_redirect_url(name: str, media_url_type: str | None = None) -> str:
    from urllib.parse import quote

    url = f"https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={quote(name, safe='')}"
    if media_url_type:
        url += f"&mediaUrlType={quote(media_url_type, safe='')}"
    return url
