"use client";

import { ExternalLink, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { confirmDialog } from "@/components/ui/Confirm";
import { toast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { Task, TaskList } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  succeeded: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
  running: "bg-brand-500/15 text-brand-300",
  queued: "bg-amber-500/15 text-amber-300",
  cancelled: "bg-white/10 text-slate-400",
};

export default function AdminLogsPage() {
  const [data, setData] = useState<TaskList | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [active, setActive] = useState<Task | null>(null);
  const [status, setStatus] = useState("all");

  const load = () => {
    const q = status === "all" ? "" : `&status=${status}`;
    api<TaskList>(`/admin/tasks?page=1&page_size=50${q}`).then(setData).catch(() => {});
  };

  useEffect(() => {
    load();
  }, [status]);

  async function openTask(publicId: string) {
    const detail = await api<Task>(`/admin/tasks/${publicId}`);
    setActive(detail);
  }

  async function batchDelete() {
    if (selected.length === 0) return;
    const ok = await confirmDialog({
      title: "批量删除任务日志",
      message: `确认删除 ${selected.length} 个任务及其日志?`,
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    await api("/admin/tasks/batch-delete", {
      method: "POST",
      body: JSON.stringify({ public_ids: selected }),
    });
    setSelected([]);
    setActive(null);
    load();
    toast.success("已删除");
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">任务日志</h1>
          <p className="page-sub">查看每个任务的请求、进度、事件日志、结果和链接地址</p>
        </div>
        <div className="flex gap-2">
          <select className="input h-9 w-32" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">全部状态</option>
            <option value="queued">排队</option>
            <option value="running">运行中</option>
            <option value="succeeded">成功</option>
            <option value="failed">失败</option>
          </select>
          <button onClick={load} className="btn-ghost">
            <RefreshCw className="h-4 w-4" />
            刷新
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="card overflow-x-auto">
          {selected.length > 0 && (
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2 text-xs text-slate-400">
              <span>已选择 {selected.length} 个任务</span>
              <button onClick={batchDelete} className="btn-ghost btn-sm text-red-300">
                <Trash2 className="h-3.5 w-3.5" />
                批量删除
              </button>
            </div>
          )}
          <table className="w-full min-w-[920px] text-[13px]">
            <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2.5">
                  <input
                    type="checkbox"
                    checked={!!data?.items.length && selected.length === data.items.length}
                    onChange={(e) => setSelected(e.target.checked ? data?.items.map((t) => t.public_id) ?? [] : [])}
                  />
                </th>
                <th className="px-4 py-2.5">任务</th>
                <th className="px-4 py-2.5">状态 / 进度</th>
                <th className="px-4 py-2.5">账号</th>
                <th className="px-4 py-2.5">请求</th>
                <th className="px-4 py-2.5">结果链接</th>
                <th className="px-4 py-2.5">时间</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((t) => (
                <tr
                  key={t.public_id}
                  className="cursor-pointer border-b border-white/[0.03] hover:bg-white/[0.02]"
                  onClick={() => openTask(t.public_id)}
                >
                  <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(t.public_id)}
                      onChange={(e) =>
                        setSelected((prev) =>
                          e.target.checked ? [...prev, t.public_id] : prev.filter((id) => id !== t.public_id)
                        )
                      }
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="font-mono text-xs text-slate-300">{t.public_id}</div>
                    <div className="mt-1 line-clamp-1 text-slate-500">{t.prompt}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={cn("badge", STATUS_STYLE[t.status])}>{t.status}</span>
                    <div className="mt-1 text-xs text-slate-400">{t.progress}%</div>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400">{t.account_id ?? "—"}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-400">
                    <div>{t.type}</div>
                    <div>{String(t.params.model ?? "default")}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    {t.outputs[0]?.url ? (
                      <a
                        href={t.outputs[0].url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-sky-300 hover:text-white"
                        onClick={(e) => e.stopPropagation()}
                      >
                        打开 <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">
                    {new Date(t.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {(!data || data.items.length === 0) && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    暂无任务日志
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="card min-h-[360px] p-4">
          {active ? (
            <div className="space-y-4">
              <div>
                <div className="text-sm text-white">任务详情</div>
                <div className="mt-1 break-all font-mono text-xs text-slate-500">{active.public_id}</div>
              </div>
              <Info title="请求参数" value={JSON.stringify({ prompt: active.prompt, params: active.params }, null, 2)} />
              <Info title="输出结果" value={JSON.stringify(active.outputs, null, 2)} />
              <div>
                <div className="mb-2 text-xs text-slate-500">事件日志</div>
                <div className="space-y-2">
                  {(active.events ?? []).map((e) => (
                    <div key={e.id} className="rounded-md border border-white/[0.06] bg-white/[0.03] p-2">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className={cn(e.level === "error" ? "text-red-300" : e.level === "warn" ? "text-amber-300" : "text-sky-300")}>
                          {e.stage}
                        </span>
                        <span className="text-slate-500">{new Date(e.created_at).toLocaleTimeString()}</span>
                      </div>
                      <div className="mt-1 text-xs text-slate-300">{e.message}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid h-full place-items-center text-sm text-slate-500">点击左侧任务查看详情</div>
          )}
        </div>
      </div>
    </div>
  );
}

function Info({ title, value }: { title: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-xs text-slate-500">{title}</div>
      <pre className="max-h-48 overflow-auto rounded-md bg-black/20 p-2 text-xs text-slate-300">{value}</pre>
    </div>
  );
}
