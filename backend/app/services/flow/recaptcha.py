"""reCAPTCHA Enterprise token + Bearer 浏览器 Oracle。

FLOW 的每次生成都需要一个新鲜的 reCAPTCHA Enterprise token,而该 token 只能在
**真实浏览器**里通过 `grecaptcha.enterprise.execute` 产生(纯 HTTP 拿不到)。同时
账号的 ya29 Bearer 会过期,需要从浏览器对 aisandbox 的请求头里实时抓取刷新。

本模块用 Playwright 打开账号的持久化 Chrome Profile:
1. 访问 labs.google/fx/tools/flow,监听对 aisandbox 的请求以捕获最新 Bearer;
2. 等待 grecaptcha.enterprise 就绪后 execute,拿到 token;
3. 顺带抓取浏览器 UA / sec-ch-ua 等头,供 HTTP 提交对齐指纹。

注意:同一持久化 Profile 不能被多个浏览器进程同时打开,调用方需对账号加锁(见 pool)。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.services.flow import protocol as P


@dataclass
class OracleResult:
    recaptcha_token: str
    bearer: str | None = None
    browser_headers: dict[str, str] = field(default_factory=dict)


class RecaptchaError(Exception):
    pass


def _token_looks_good(tok: str | None) -> bool:
    # 经验:正常浏览器 enterprise token 以 0cAF 开头;HF 前缀多为低分/风控失败。
    if not tok or len(tok) < 1000:
        return False
    return not tok.startswith("HF")


async def _run_oracle(profile_dir: str, action: str) -> OracleResult:
    from playwright.async_api import async_playwright

    captured = {"bearer": None, "headers": {}}

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            profile_dir,
            headless=settings.FLOW_HEADLESS,
            viewport={"width": 1280, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-device-scale-factor=1",
            ],
        )

        def on_request(req):
            try:
                if "aisandbox-pa.googleapis.com" in req.url:
                    auth = req.headers.get("authorization") or req.headers.get("Authorization") or ""
                    if isinstance(auth, str) and auth.lower().startswith("bearer ya29."):
                        captured["bearer"] = auth[7:].strip()
                    captured["headers"] = {
                        k: v
                        for k, v in req.headers.items()
                        if k.lower()
                        in ("user-agent", "accept-language", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform")
                    }
            except Exception:  # noqa: BLE001
                pass

        ctx.on("request", on_request)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto(P.FLOW_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:  # noqa: BLE001
            await ctx.close()
            raise RecaptchaError(f"打开 Flow 页面失败: {exc}") from exc

        # 等 bearer 出现(短轮询)
        for _ in range(25):
            if captured["bearer"]:
                break
            await asyncio.sleep(0.2)

        try:
            await page.wait_for_function(
                "() => window.grecaptcha && window.grecaptcha.enterprise && window.grecaptcha.enterprise.execute",
                timeout=settings.FLOW_TOKEN_TIMEOUT * 1000,
            )
            token = None
            for _attempt in range(3):
                token = await page.evaluate(
                    """async ({siteKey, action}) => {
                        await new Promise((resolve) => window.grecaptcha.enterprise.ready(resolve));
                        return await window.grecaptcha.enterprise.execute(siteKey, {action});
                    }""",
                    {"siteKey": P.RECAPTCHA_SITE_KEY, "action": action},
                )
                if _token_looks_good(token):
                    break
                await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            raise RecaptchaError(f"获取 reCAPTCHA token 失败: {exc}") from exc
        finally:
            # execute 后页面可能再发 aisandbox 请求,再等一下抓 bearer
            for _ in range(10):
                if captured["bearer"]:
                    break
                await asyncio.sleep(0.2)
            await ctx.close()

        if not _token_looks_good(token):
            raise RecaptchaError("reCAPTCHA token 质量不合格")

        return OracleResult(
            recaptcha_token=token,
            bearer=captured["bearer"],
            browser_headers=captured["headers"] or {},
        )


def get_token_and_bearer(profile_dir: str, action: str = P.ACTION_VIDEO) -> OracleResult:
    """同步入口(供 Celery worker 调用)。"""
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run_oracle(profile_dir, action))
