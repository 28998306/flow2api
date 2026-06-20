"use client";

import { Download, Film, ImageIcon, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { confirmDialog } from "@/components/ui/Confirm";
import { toast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { Task, TaskList, TaskType } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  succeeded: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
  running: "bg-brand-500/15 text-brand-300",
  queued: "bg-amber-500/15 text-amber-300",
  cancelled: "bg-white/10 text-slate-400",
};

const STATUS_LABEL: Record<string, string> = {
  succeeded: "完成",
  failed: "失败",
  running: "生成中",
  queued: "排队中",
  cancelled: "已取消",
};

export default function HistoryPage() {
  const [filter, setFilter] = useState<TaskType | "all">("all");
  const [data, setData] = useState<TaskList | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    const q = filter === "all" ? "" : `&type=${filter}`;
    api<TaskList>(`/generate/tasks?page=1&page_size=60${q}`)
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [filter]);

  async function deleteFailed() {
    const failedCount = data?.items.filter((item) => item.status === "failed").length ?? 0;
    const ok = await confirmDialog({
      title: "删除失败作品",
      message: failedCount
        ? `确认删除你的所有失败任务? 当前页有 ${failedCount} 个失败任务。`
        : "确认删除你的所有失败任务?",
      confirmText: "删除失败",
      danger: true,
    });
    if (!ok) return;
    const res = await api<{ deleted: number }>("/generate/tasks/delete-failed", { method: "POST" });
    load();
    toast.success(`已删除 ${res.deleted} 个失败任务`);
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">我的作品</h1>
          <p className="page-sub">
            共 {data?.total ?? 0} 个生成任务
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md bg-ink-900/60 p-1">
            {([
              { id: "all", label: "全部" },
              { id: "image", label: "图片" },
              { id: "video", label: "视频" },
            ] as const).map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={cn(
                  "rounded px-3.5 py-1 text-[13px] transition",
                  filter === f.id
                    ? "bg-brand-500 text-white"
                    : "text-slate-400 hover:text-slate-200"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <button onClick={deleteFailed} className="btn-ghost text-red-300">
            <Trash2 className="h-4 w-4" />
            删除失败
          </button>
        </div>
      </div>

      {loading ? (
        <Grid>
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-md bg-white/5"
            />
          ))}
        </Grid>
      ) : data && data.items.length > 0 ? (
        <Grid>
          {data.items.map((t) => (
            <TaskCard key={t.public_id} task={t} />
          ))}
        </Grid>
      ) : (
        <div className="mt-20 text-center text-slate-500">
          还没有作品,去工作台开始创作吧。
        </div>
      )}
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {children}
    </div>
  );
}

function TaskCard({ task }: { task: Task }) {
  const out = task.outputs[0];
  return (
    <div className="card group overflow-hidden">
      <div className="relative aspect-square bg-ink-900/60">
        {out ? (
          out.type === "video" ? (
            <video
              src={out.url}
              className="h-full w-full object-cover"
              controls
              muted
              playsInline
              preload="metadata"
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={out.url} alt={task.prompt} className="h-full w-full object-cover" />
          )
        ) : (
          <div className="grid h-full place-items-center text-slate-600">
            {task.type === "video" ? (
              <Film className="h-8 w-8" />
            ) : (
              <ImageIcon className="h-8 w-8" />
            )}
          </div>
        )}
        <span
          className={cn(
            "absolute left-2 top-2 rounded px-2 py-0.5 text-[10px]",
            STATUS_STYLE[task.status]
          )}
        >
          {STATUS_LABEL[task.status]}
        </span>
        {out && (
          <a
            href={out.url}
            download
            target="_blank"
            rel="noreferrer"
            className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-md bg-black/50 text-white opacity-0 backdrop-blur transition group-hover:opacity-100"
          >
            <Download className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
      <div className="p-3">
        <p className="line-clamp-2 text-xs text-slate-300">{task.prompt}</p>
        <p className="mt-1.5 text-[10px] text-slate-500">
          {new Date(task.created_at).toLocaleString("zh-CN")}
        </p>
      </div>
    </div>
  );
}
