# Flow2API — 多用户 AIGC 出图 / 出视频平台

一个面向商用的多用户 AIGC 平台:前台用户用 **FLOW** 出图 / 出视频,后台管理员配置账号池、额度与监控。架构按 **高并发 / 水平扩展** 设计。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI (异步) |
| 任务队列 | Celery + Redis(出图 / 出视频分队列) |
| 实时进度 | WebSocket |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) + Alembic |
| 缓存 / 限流 / 锁 / 队列 | Redis |
| 对象存储 | MinIO (S3 兼容) |
| 前端 | Next.js (App Router) + TypeScript + Tailwind + Framer Motion |
| 部署 | Docker Compose(本地)/ K8s(生产) |

## 架构概览

```
浏览器(Next.js)
   │ HTTPS / WSS
Nginx 负载均衡
   │
FastAPI 集群 ──→ PostgreSQL
   │   │
   │   └──→ Redis(队列 / 缓存 / 分布式锁 / 限流)
   │             │
   │        Celery Workers(出图队列 / 出视频队列)
   │             │
   │        FLOW 适配层(账号池 + 并发闸门)──→ FLOW
   │             │
   └──进度 WS──┘ 生成结果 ──→ MinIO / S3
```

## 高并发设计要点

1. **请求/执行解耦**:HTTP 仅入队并返回 `task_id`,真正生成在 Worker 执行。
2. **账号池 + 并发闸门**:Redis 信号量限制对 FLOW 的最大并发,多账号轮询 + 故障转移。
3. **用户级限流与额度**:Redis 计数器实现按用户/按天的额度与频控。
4. **分队列**:出图(快)与出视频(慢)分队列、分 worker,互不阻塞。
5. **无状态横向扩展**:API 与 Worker 均无状态,可任意扩容。

## 本地启动

```bash
cp .env.example .env
docker compose up -d --build
# 前端:   http://localhost:3000
# 后端文档: http://localhost:8000/docs
# MinIO:   http://localhost:9001  (minioadmin / minioadmin)
```

首次启动后初始化数据库与管理员账号:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed
```

## 目录结构

```
flow2api/
├── backend/        FastAPI + Celery
│   └── app/
│       ├── core/       配置 / DB / Redis / 安全
│       ├── models/     SQLAlchemy 模型
│       ├── schemas/    Pydantic schema
│       ├── api/        路由(auth / generation / admin / ws)
│       ├── services/   FLOW 适配层 / 账号池 / 额度
│       ├── workers/    Celery 任务
│       └── scripts/    seed 等脚本
├── frontend/       Next.js 前台 + 管理员后台
└── docker-compose.yml
```

## FLOW 接入说明(真实 Google Flow / Labs FX 协议)

适配层位于 `backend/app/services/flow/`,按真实协议实现:

- `protocol.py`:API 基址 `aisandbox-pa.googleapis.com`、工具名 `PINHOLE`、端点、模型/比例映射、请求体构造。
- `client.py`:出视频(`video:batchAsyncGenerateVideoText` → 轮询 `batchCheckAsyncVideoGenerationStatus` → `media/{name}` 取 base64)、出图(`image:batchGenerateImages`)、错误分类(鉴权/配额/限流/可重试),可选 curl_cffi 模拟 Chrome TLS 指纹。
- `recaptcha.py`:Playwright 打开账号 Chrome Profile,实时抓取 ya29 Bearer + 执行 `grecaptcha.enterprise.execute` 拿到 reCAPTCHA token + 浏览器指纹头。
- `pool.py`:账号池选号、全局/单账号并发闸门、Profile 进程级互斥锁、按错误类型冷却(配额长冷却、鉴权/限流短冷却)、Bearer 刷新。

### 账号 = Google 账号 + Chrome Profile

每个 FLOW 账号对应一个登录了 labs.google 的 Google 账号及其持久化 Chrome Profile
(目录名相对 `FLOW_PROFILES_DIR`,卷 `flow_profiles` 挂载到 worker 的 `/data/flow_profiles`)。

**首次启用一个账号(登录引导,需有界面的环境):**

```bash
# 在 worker 容器内,以有头浏览器打开该 Profile 登录 Google,登录后关闭即可
docker compose exec worker_image python - <<'PY'
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/data/flow_profiles/acc1", headless=False)
        await ctx.pages[0].goto("https://labs.google/fx/tools/flow")
        await asyncio.sleep(180)  # 手动完成 Google 登录
        await ctx.close()
asyncio.run(main())
PY
```

> 生产环境通常在一台有图形界面的机器上批量完成各 Profile 的登录,再把 `flow_profiles`
> 卷同步到服务器;之后系统即可在 headless 模式下自动刷新 Bearer / reCAPTCHA 并出图出视频。

随后在「管理后台 → 账号池」新增账号,填 `chrome_profile=acc1` 即可。系统会自动:
抓取/刷新 Bearer、生成 reCAPTCHA、按并发与配额调度、失败冷却换号。

> 出图/出视频 Worker 使用 `backend/Dockerfile.worker`(基于官方 Playwright 镜像,内置 Chromium)。
