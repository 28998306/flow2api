export type TaskType = "image" | "video";
export type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface Output {
  url: string;
  type: TaskType;
}

export interface Task {
  public_id: string;
  account_id?: number | null;
  celery_task_id?: string | null;
  type: TaskType;
  status: TaskStatus;
  progress: number;
  prompt: string;
  params: Record<string, unknown>;
  outputs: Output[];
  error: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at: string | null;
  events?: TaskEvent[];
}

export interface TaskEvent {
  id: number;
  level: "info" | "warn" | "error" | string;
  stage: string;
  message: string;
  progress: number | null;
  account_id: number | null;
  request: Record<string, unknown> | null;
  response: Record<string, unknown> | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface TaskList {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
}

export interface QuotaUsage {
  daily_image_quota: number;
  daily_image_used: number;
  daily_video_quota: number;
  daily_video_used: number;
}

export interface FlowAccount {
  id: number;
  label: string;
  email: string | null;
  chrome_profile: string;
  project_id: string | null;
  proxy: string | null;
  account_type: "normal" | "pro" | "ula";
  paygate_tier: string | null;
  remaining_credits: number | null;
  status: "active" | "disabled" | "cooldown" | "invalid";
  weight: number;
  max_concurrency: number;
  success_count: number;
  fail_count: number;
  last_error: string | null;
  last_used_at: string | null;
  last_bearer_refresh: string | null;
  bearer_expires_at: string | null;
  cookies_expires_at: string | null;
  next_refresh_at: string | null;
  auto_refresh_minutes: number;
  has_bearer: boolean;
  has_session_token: boolean;
  has_google_cookies: boolean;
  created_at: string;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  role: "user" | "admin";
  is_active: boolean;
  daily_image_quota: number;
  daily_video_quota: number;
  created_at: string;
}

export interface Dashboard {
  total_users: number;
  total_tasks: number;
  active_accounts: number;
  tasks_by_status: Record<string, number>;
  last_24h_tasks: number;
  last_24h_images: number;
  last_24h_videos: number;
  running: number;
  queued: number;
}

export interface ModelInfo {
  id: string;
  object: "model";
  type: TaskType;
  label: string;
  provider: string;
  account_types: string[];
  supports_4k: boolean;
  supports_image_input: boolean;
  description: string | null;
}

export interface ApiKeyInfo {
  id: number;
  user_id: number | null;
  name: string;
  prefix: string;
  status: "active" | "disabled";
  scopes: string[];
  note: string | null;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}
