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
  type: TaskType;
  status: TaskStatus;
  progress: number;
  prompt: string;
  params: Record<string, unknown>;
  outputs: Output[];
  error: string | null;
  created_at: string;
  finished_at: string | null;
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
  has_bearer: boolean;
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
