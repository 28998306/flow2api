"use client";

import { Plus, Power, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { FlowAccount } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-500/15 text-emerald-300",
  disabled: "bg-slate-500/15 text-slate-300",
  cooldown: "bg-amber-500/15 text-amber-300",
  invalid: "bg-red-500/15 text-red-300",
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<FlowAccount[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    label: "",
    email: "",
    chrome_profile: "",
    project_id: "",
    bearer_token: "",
    weight: 1,
    max_concurrency: 2,
  });

  const load = () => api<FlowAccount[]>("/admin/accounts").then(setAccounts).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!form.label || !form.chrome_profile) return;
    await api("/admin/accounts", { method: "POST", body: JSON.stringify(form) });
    setForm({ label: "", email: "", chrome_profile: "", project_id: "", bearer_token: "", weight: 1, max_concurrency: 2 });
    setShowForm(false);
    load();
  }

  async function toggle(a: FlowAccount) {
    const status = a.status === "active" ? "disabled" : "active";
    await api(`/admin/accounts/${a.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    load();
  }

  async function remove(id: number) {
    if (!confirm("确认删除该账号?")) return;
    await api(`/admin/accounts/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">FLOW 账号池</h1>
          <p className="mt-1 text-sm text-slate-400">
            每个账号 = 一个登录 labs.google 的 Google 账号 + 持久化 Chrome Profile,系统自动刷新 Bearer 与 reCAPTCHA
          </p>
        </div>
        <button onClick={() => setShowForm((s) => !s)} className="btn-primary">
          <Plus className="h-4 w-4" />
          新增账号
        </button>
      </div>

      {showForm && (
        <div className="card mt-6 space-y-4 p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">名称</label>
              <input
                className="input"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder="账号-01"
              />
            </div>
            <div>
              <label className="label">Google 邮箱(可选)</label>
              <input
                className="input"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="user@gmail.com"
              />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Chrome Profile 目录名</label>
              <input
                className="input font-mono"
                value={form.chrome_profile}
                onChange={(e) => setForm({ ...form, chrome_profile: e.target.value })}
                placeholder="acc1  (相对 FLOW_PROFILES_DIR)"
              />
            </div>
            <div>
              <label className="label">Project ID(可选)</label>
              <input
                className="input font-mono"
                value={form.project_id}
                onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                placeholder="留空自动获取"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:max-w-xs">
            <div>
              <label className="label">权重</label>
              <input
                type="number"
                className="input"
                value={form.weight}
                onChange={(e) => setForm({ ...form, weight: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label">最大并发</label>
              <input
                type="number"
                className="input"
                value={form.max_concurrency}
                onChange={(e) => setForm({ ...form, max_concurrency: Number(e.target.value) })}
              />
            </div>
          </div>
          <div>
            <label className="label">Bearer Token(可选,系统会自动从浏览器刷新)</label>
            <textarea
              className="input min-h-[60px] resize-none font-mono text-xs"
              value={form.bearer_token}
              onChange={(e) => setForm({ ...form, bearer_token: e.target.value })}
              placeholder="ya29...."
            />
          </div>
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200/80">
            提示:首次使用需先在对应 Chrome Profile 里登录该 Google 账号(headed 模式),之后系统即可在该 Profile 上自动出图出视频。
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={() => setShowForm(false)} className="btn-ghost">
              取消
            </button>
            <button onClick={create} className="btn-primary">
              保存
            </button>
          </div>
        </div>
      )}

      <div className="card mt-6 overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-5 py-3">名称 / 邮箱</th>
              <th className="px-5 py-3">状态</th>
              <th className="px-5 py-3">Bearer</th>
              <th className="px-5 py-3">额度</th>
              <th className="px-5 py-3">权重/并发</th>
              <th className="px-5 py-3">成功/失败</th>
              <th className="px-5 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                <td className="px-5 py-3">
                  <div className="font-medium text-white">{a.label}</div>
                  <div className="text-xs text-slate-500">{a.email || a.chrome_profile}</div>
                </td>
                <td className="px-5 py-3">
                  <span className={cn("rounded-full px-2 py-0.5 text-xs", STATUS_STYLE[a.status])}>
                    {a.status}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-xs",
                      a.has_bearer ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-500/15 text-slate-400"
                    )}
                  >
                    {a.has_bearer ? "已就绪" : "待登录"}
                  </span>
                </td>
                <td className="px-5 py-3 text-slate-300">{a.remaining_credits ?? "—"}</td>
                <td className="px-5 py-3 text-slate-300">
                  {a.weight} / {a.max_concurrency}
                </td>
                <td className="px-5 py-3 text-slate-300">
                  <span className="text-emerald-300">{a.success_count}</span> /{" "}
                  <span className="text-red-300">{a.fail_count}</span>
                </td>
                <td className="px-5 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => toggle(a)}
                      className="grid h-8 w-8 place-items-center rounded-lg glass text-slate-300 hover:text-white"
                      title="启用/禁用"
                    >
                      <Power className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => remove(a.id)}
                      className="grid h-8 w-8 place-items-center rounded-lg glass text-red-300 hover:bg-red-500/10"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-slate-500">
                  暂无账号,点击右上角新增
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
