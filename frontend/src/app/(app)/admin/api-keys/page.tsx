"use client";

import { Copy, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { confirmDialog } from "@/components/ui/Confirm";
import { toast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ApiKeyInfo } from "@/lib/types";

export default function ApiKeysPage() {
  const [items, setItems] = useState<ApiKeyInfo[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [name, setName] = useState("default");
  const [createdKey, setCreatedKey] = useState("");

  const load = () => api<ApiKeyInfo[]>("/admin/api-keys").then(setItems).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  async function create() {
    const row = await api<ApiKeyInfo & { key: string }>("/admin/api-keys", {
      method: "POST",
      body: JSON.stringify({ name, scopes: ["image", "video", "models"] }),
    });
    setCreatedKey(row.key);
    setName("default");
    load();
    toast.success("API Key 已创建,请立即保存完整 key");
  }

  async function copy(text: string) {
    await navigator.clipboard.writeText(text);
    toast.success("已复制");
  }

  async function batchDelete() {
    if (selected.length === 0) return;
    const ok = await confirmDialog({
      title: "批量删除 API Key",
      message: `确认删除选中的 ${selected.length} 个 Key?`,
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    await api("/admin/api-keys/batch-delete", {
      method: "POST",
      body: JSON.stringify({ ids: selected }),
    });
    setSelected([]);
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">下游 API Key</h1>
          <p className="page-sub">用于 OpenAI 兼容接口: `/v1/models`, `/v1/images/generations`, `/v1/videos/generations`</p>
        </div>
      </div>

      <div className="card mt-4 space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Key 名称" />
          <button onClick={create} className="btn-primary">
            <Plus className="h-4 w-4" />
            创建 Key
          </button>
        </div>
        {createdKey && (
          <div className="rounded-md border border-emerald-400/20 bg-emerald-500/10 p-3">
            <div className="text-xs text-emerald-300">完整 Key 只显示一次</div>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all text-xs text-white">{createdKey}</code>
              <button onClick={() => copy(createdKey)} className="btn-ghost btn-sm">
                <Copy className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card mt-4 overflow-x-auto">
        {selected.length > 0 && (
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2 text-xs text-slate-400">
            <span>已选择 {selected.length} 个 Key</span>
            <button onClick={batchDelete} className="btn-ghost btn-sm text-red-300">
              <Trash2 className="h-3.5 w-3.5" />
              批量删除
            </button>
          </div>
        )}
        <table className="w-full min-w-[760px] text-[13px]">
          <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2.5">
                <input
                  type="checkbox"
                  checked={items.length > 0 && selected.length === items.length}
                  onChange={(e) => setSelected(e.target.checked ? items.map((i) => i.id) : [])}
                />
              </th>
              <th className="px-4 py-2.5">名称</th>
              <th className="px-4 py-2.5">前缀</th>
              <th className="px-4 py-2.5">状态</th>
              <th className="px-4 py-2.5">权限</th>
              <th className="px-4 py-2.5">最后使用</th>
              <th className="px-4 py-2.5">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-white/[0.03]">
                <td className="px-4 py-2.5">
                  <input
                    type="checkbox"
                    checked={selected.includes(item.id)}
                    onChange={(e) =>
                      setSelected((prev) => e.target.checked ? [...prev, item.id] : prev.filter((id) => id !== item.id))
                    }
                  />
                </td>
                <td className="px-4 py-2.5 text-white">{item.name}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-300">{item.prefix}...</td>
                <td className="px-4 py-2.5">
                  <span className="badge bg-emerald-500/15 text-emerald-300">{item.status}</span>
                </td>
                <td className="px-4 py-2.5 text-slate-400">{item.scopes.join(", ")}</td>
                <td className="px-4 py-2.5 text-slate-500">{item.last_used_at ? new Date(item.last_used_at).toLocaleString() : "—"}</td>
                <td className="px-4 py-2.5 text-slate-500">{new Date(item.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
