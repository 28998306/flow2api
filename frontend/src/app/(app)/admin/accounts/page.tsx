"use client";

import { CheckCircle2, Plus, Power, Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { confirmDialog } from "@/components/ui/Confirm";
import { toast } from "@/components/ui/Toast";
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
  const [showImport, setShowImport] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [importText, setImportText] = useState("");
  const [form, setForm] = useState({
    label: "",
    email: "",
    project_id: "",
    session_token: "",
    google_cookies: "",
    proxy: "",
    account_type: "normal",
    cookies_expires_at: "",
    auto_refresh_minutes: 50,
    weight: 1,
    max_concurrency: 2,
  });

  const load = () => api<FlowAccount[]>("/admin/accounts").then(setAccounts).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!form.label || !form.session_token || !form.project_id) {
      toast.warn("请填写名称、Session Token(ST)与 Project ID");
      return;
    }
    try {
      const payload = {
        ...form,
        cookies_expires_at: form.cookies_expires_at || null,
      };
      await api("/admin/accounts", { method: "POST", body: JSON.stringify(payload) });
      setForm({
        label: "",
        email: "",
        project_id: "",
        session_token: "",
        google_cookies: "",
        proxy: "",
        account_type: "normal",
        cookies_expires_at: "",
        auto_refresh_minutes: 50,
        weight: 1,
        max_concurrency: 2,
      });
      setShowForm(false);
      load();
      toast.success("账号已新增");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "新增失败");
    }
  }

  async function batchImport() {
    try {
      const parsed = JSON.parse(importText);
      const accountsPayload = Array.isArray(parsed) ? parsed : parsed.accounts;
      if (!Array.isArray(accountsPayload)) {
        toast.warn("请输入账号数组或 { accounts: [...] }");
        return;
      }
      const res = await api<{ created: number; skipped: number; errors: string[] }>(
        "/admin/accounts/import",
        { method: "POST", body: JSON.stringify({ accounts: accountsPayload }) }
      );
      toast.success(`导入完成: 新增 ${res.created}, 跳过 ${res.skipped}`);
      if (res.errors.length) toast.warn(res.errors[0]);
      setImportText("");
      setShowImport(false);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "导入失败");
    }
  }

  async function batchDelete() {
    if (selected.length === 0) return;
    const ok = await confirmDialog({
      title: "批量删除账号",
      message: `确认删除选中的 ${selected.length} 个账号?`,
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    await api("/admin/accounts/batch-delete", {
      method: "POST",
      body: JSON.stringify({ ids: selected }),
    });
    setSelected([]);
    load();
    toast.success("已批量删除");
  }

  async function test(a: FlowAccount) {
    try {
      const r = await api<{ email: string | null; expires_at: string }>(
        `/admin/accounts/${a.id}/test`,
        { method: "POST" }
      );
      toast.success(`凭证有效:${r.email ?? "?"}(令牌至 ${new Date(r.expires_at).toLocaleString()})`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "校验失败");
    }
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
    const ok = await confirmDialog({
      title: "删除账号",
      message: "删除后该账号将从账号池移除,确认继续?",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    await api(`/admin/accounts/${id}`, { method: "DELETE" });
    load();
    toast.success("账号已删除");
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">FLOW 账号池</h1>
          <p className="page-sub">
            每个账号 = Session Token(ST)+ Project ID + Google Cookies,系统纯 HTTP 刷新 access token 并获取 reCAPTCHA
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowImport((s) => !s)} className="btn-ghost shrink-0">
            <Upload className="h-4 w-4" />
            批量导入
          </button>
          <button onClick={() => setShowForm((s) => !s)} className="btn-primary shrink-0">
            <Plus className="h-4 w-4" />
            新增账号
          </button>
        </div>
      </div>

      {showImport && (
        <div className="card mt-4 space-y-3 p-4">
          <div>
            <label className="label">批量导入 JSON</label>
            <textarea
              className="input min-h-[160px] resize-none font-mono text-xs"
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='[{"label":"acc1","session_token":"...","project_id":"...","account_type":"pro","proxy":"...","google_cookies":"..."}]'
            />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowImport(false)} className="btn-ghost">取消</button>
            <button onClick={batchImport} className="btn-primary">导入</button>
          </div>
        </div>
      )}

      {showForm && (
        <div className="card mt-4 space-y-3.5 p-4">
          <div className="grid gap-3.5 sm:grid-cols-2">
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
          <div>
            <label className="label">Project ID</label>
            <input
              className="input font-mono"
              value={form.project_id}
              onChange={(e) => setForm({ ...form, project_id: e.target.value })}
              placeholder="0131165a-627e-... (labs.google flow 项目 URL 里的 project id)"
            />
          </div>
          <div>
            <label className="label">专用代理(可选,留空用全局)</label>
            <input
              className="input font-mono text-xs"
              value={form.proxy}
              onChange={(e) => setForm({ ...form, proxy: e.target.value })}
              placeholder="http://user:pass@host:port 或 socks5://user:pass@host:port"
            />
          </div>
          <div className="grid grid-cols-2 gap-3.5 sm:max-w-xs">
            <div>
              <label className="label">账号类型</label>
              <select
                className="input"
                value={form.account_type}
                onChange={(e) => setForm({ ...form, account_type: e.target.value })}
              >
                <option value="normal">普号</option>
                <option value="pro">PRO</option>
                <option value="ula">ULA</option>
              </select>
            </div>
            <div>
              <label className="label">自动刷新(分钟)</label>
              <input
                type="number"
                className="input"
                value={form.auto_refresh_minutes}
                onChange={(e) => setForm({ ...form, auto_refresh_minutes: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3.5 sm:max-w-xl">
            <div>
              <label className="label">Cookies 有效期(可选)</label>
              <input
                type="datetime-local"
                className="input"
                value={form.cookies_expires_at}
                onChange={(e) => setForm({ ...form, cookies_expires_at: e.target.value })}
              />
            </div>
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
            <label className="label">Session Token(ST · __Secure-next-auth.session-token)</label>
            <textarea
              className="input min-h-[72px] resize-none font-mono text-xs"
              value={form.session_token}
              onChange={(e) => setForm({ ...form, session_token: e.target.value })}
              placeholder="eyJhbGciOiJkaXIiLCJlbmMi...(浏览器 labs.google Cookie 里复制)"
            />
          </div>
          <div>
            <label className="label">Google Cookies(推荐,用于纯协议 reCAPTCHA)</label>
            <textarea
              className="input min-h-[88px] resize-none font-mono text-xs"
              value={form.google_cookies}
              onChange={(e) => setForm({ ...form, google_cookies: e.target.value })}
              placeholder='从 Cookie Editor 导出 .google.com + accounts.google.com cookies JSON,需包含 SID/HSID/SSID/APISID/SAPISID 等'
            />
          </div>
          <div className="alert-warn">
            无头 broker 会自动获取 reCAPTCHA token。建议同一账号固定代理,并填写 Google Cookies 提升评分。
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="btn-ghost">
              取消
            </button>
            <button onClick={create} className="btn-primary">
              保存
            </button>
          </div>
        </div>
      )}

      <div className="card mt-4 overflow-x-auto">
        {selected.length > 0 && (
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2 text-xs text-slate-400">
            <span>已选择 {selected.length} 个账号</span>
            <button onClick={batchDelete} className="btn-ghost btn-sm text-red-300">
              批量删除
            </button>
          </div>
        )}
        <table className="w-full min-w-[1080px] text-[13px]">
          <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2.5">
                <input
                  type="checkbox"
                  checked={accounts.length > 0 && selected.length === accounts.length}
                  onChange={(e) => setSelected(e.target.checked ? accounts.map((a) => a.id) : [])}
                />
              </th>
              <th className="px-4 py-2.5">名称 / 邮箱</th>
              <th className="px-4 py-2.5">状态</th>
              <th className="px-4 py-2.5">类型</th>
              <th className="px-4 py-2.5">凭证</th>
              <th className="px-4 py-2.5">有效期 / 刷新</th>
              <th className="px-4 py-2.5">额度</th>
              <th className="px-4 py-2.5">权重/并发</th>
              <th className="px-4 py-2.5">成功/失败</th>
              <th className="px-4 py-2.5 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                <td className="px-4 py-2.5">
                  <input
                    type="checkbox"
                    checked={selected.includes(a.id)}
                    onChange={(e) =>
                      setSelected((prev) =>
                        e.target.checked ? [...prev, a.id] : prev.filter((id) => id !== a.id)
                      )
                    }
                  />
                </td>
                <td className="px-4 py-2.5">
                  <div className="text-white">{a.label}</div>
                  <div className="text-xs text-slate-500">{a.email || a.chrome_profile}</div>
                </td>
                <td className="px-4 py-2.5">
                  <span className={cn("badge", STATUS_STYLE[a.status])}>
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span className="badge bg-brand-500/15 text-brand-300">
                    {a.account_type === "normal" ? "普号" : a.account_type.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={cn(
                      "badge",
                      a.has_session_token ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"
                    )}
                  >
                    {a.has_session_token ? "ST" : "缺 ST"}
                  </span>
                  <span
                    className={cn(
                      "badge ml-1",
                      a.has_google_cookies ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
                    )}
                  >
                    {a.has_google_cookies ? "G-Cookies" : "缺 Cookies"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-slate-400">
                  <div>Cookies: {a.cookies_expires_at ? new Date(a.cookies_expires_at).toLocaleString() : "未设置"}</div>
                  <div>下次刷新: {a.next_refresh_at ? new Date(a.next_refresh_at).toLocaleString() : "—"}</div>
                </td>
                <td className="px-4 py-2.5 text-slate-300">{a.remaining_credits ?? "—"}</td>
                <td className="px-4 py-2.5 text-slate-300">
                  {a.weight} / {a.max_concurrency}
                </td>
                <td className="px-4 py-2.5 text-slate-300">
                  <span className="text-emerald-300">{a.success_count}</span> /{" "}
                  <span className="text-red-300">{a.fail_count}</span>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => test(a)}
                      className="grid h-7 w-7 place-items-center rounded-md glass text-sky-300 hover:text-white"
                      title="校验 ST 凭证"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => toggle(a)}
                      className="grid h-7 w-7 place-items-center rounded-md glass text-slate-300 hover:text-white"
                      title="启用/禁用"
                    >
                      <Power className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => remove(a.id)}
                      className="grid h-7 w-7 place-items-center rounded-md glass text-red-300 hover:bg-red-500/10"
                      title="删除"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-10 text-center text-slate-500">
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
