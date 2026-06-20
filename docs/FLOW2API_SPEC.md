# Flow2API 功能规范

## 任务日志规范

每个生成任务都必须记录事件日志，覆盖以下阶段：

- `started`：任务开始执行。
- `account_acquired`：账号池选择成功，记录账号 ID 和账号类型。
- `token_refresh`：Labs access token 刷新或校验。
- `recaptcha`：无头 broker 或 HTTP 兜底获取 reCAPTCHA token。
- `flow_submit`：提交 Flow 协议请求，记录 prompt 和 params。
- `flow_result`：Flow 返回成功，记录输出数量和剩余额度。
- `storage`：媒体转存 MinIO / 本地媒体目录。
- `completed`：任务完成，记录结果链接。
- `flow_error` / `failed`：记录失败阶段和错误信息。

管理员通过 `/api/v1/admin/tasks` 查看任务列表，通过 `/api/v1/admin/tasks/{public_id}` 查看任务详情和事件日志。

## 账号管理规范

账号类型分为：

- `normal`：普通账号，支持基础出图和 OMNI 视频。
- `pro`：PRO 账号，支持 Pro 图片模型和高质量视频模型。
- `ula`：ULA 账号，支持所有模型，并且只有 ULA 账号允许承载 4K 图片任务。

账号需要维护：

- `session_token`：Labs `__Secure-next-auth.session-token`。
- `google_cookies`：Google / Labs cookies，用于刷新 session 和提高 reCAPTCHA 评分。
- `cookies_expires_at`：cookies 有效期，可手动填，也可从 cookies JSON 自动推算。
- `bearer_expires_at`：当前 access token 过期时间。
- `next_refresh_at`：建议自动刷新时间。
- `auto_refresh_minutes`：提前刷新分钟数。
- `proxy`：账号专用代理，优先级高于全局 `FLOW_PROXY`。

账号支持批量导入、批量删除、批量更新状态/类型/代理/并发。

## 模型规范

模型列表统一由 `/api/v1/generate/models` 和 OpenAI 兼容 `/v1/models` 输出。

当前模型：

- 图片：`nano_banana`、`banana_pro`、`imagen`、`imagen_4k`。
- 视频：`omni_flash`、`veo_3_1_fast`、`veo_3_1_lite`、`veo_3_1_quality`。

模型权限由账号类型控制。`imagen_4k` 只允许 ULA 账号执行。

## OpenAI 兼容接口规范

下游调用使用独立 API Key，格式为 `Authorization: Bearer f2a_xxx`。

接口：

- `GET /v1/models`：获取模型列表。
- `POST /v1/images/generations`：提交图片生成任务。
- `POST /v1/videos/generations`：提交视频生成任务。
- `GET /v1/tasks/{public_id}`：查询任务状态、日志和输出结果。

生成接口返回异步任务对象，包含 `id`、`status` 和 `task_url`。下游应轮询 `/v1/tasks/{public_id}` 获取结果链接。

## 批量操作规范

管理员后台的列表型资源默认支持批量操作：

- 账号池：批量导入、批量删除、批量更新。
- 任务日志：批量删除。
- 下游 API Key：批量删除。

后续新增内容管理模块时，应沿用 `{ ids: [...] }` 或 `{ public_ids: [...] }` 的批量请求格式。
