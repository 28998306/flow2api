"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Download, Film, ImageIcon, Loader2, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { toast } from "@/components/ui/Toast";
import type { ModelInfo, QuotaUsage } from "@/lib/types";
import { useTaskProgress } from "@/lib/useTaskProgress";
import { cn } from "@/lib/utils";

type Mode = "image" | "video";

const IMAGE_RATIOS = ["1:1", "3:4", "4:3", "16:9", "9:16"];
const VIDEO_RATIOS = ["16:9", "9:16", "1:1"];

export default function WorkbenchPage() {
  const [mode, setMode] = useState<Mode>("image");
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState("");
  const [ratio, setRatio] = useState("1:1");
  const [model, setModel] = useState("nano_banana");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [numOutputs, setNumOutputs] = useState(1);
  const [duration, setDuration] = useState(5);
  const [submitting, setSubmitting] = useState(false);
  const [quota, setQuota] = useState<QuotaUsage | null>(null);

  const { state, track, reset } = useTaskProgress();

  const loadQuota = () =>
    api<QuotaUsage>("/users/me/quota").then(setQuota).catch(() => {});

  useEffect(() => {
    loadQuota();
    api<{ data: ModelInfo[] }>("/generate/models").then((res) => setModels(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    setRatio(mode === "image" ? "1:1" : "16:9");
    setModel(mode === "image" ? "nano_banana" : "omni_flash");
  }, [mode]);

  useEffect(() => {
    if (state.status === "succeeded" || state.status === "failed") loadQuota();
  }, [state.status]);

  async function generate() {
    if (!prompt.trim()) return;
    setSubmitting(true);
    reset();
    try {
      const body =
        mode === "image"
          ? {
              prompt,
              model,
              negative_prompt: negative || undefined,
              aspect_ratio: ratio,
              num_outputs: numOutputs,
            }
          : { prompt, model, aspect_ratio: ratio, duration, resolution: "VIDEO_RESOLUTION_1080P" };
      const res = await api<{ public_id: string }>(`/generate/${mode}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      track(res.public_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  const busy =
    submitting ||
    state.status === "queued" ||
    state.status === "running";

  return (
    <div>
      <Header />

      <div className="mt-5 grid gap-4 xl:grid-cols-[340px_1fr]">
        {/* 参数面板 */}
        <div className="card h-fit p-4">
          <ModeSwitch mode={mode} setMode={setMode} />

          <div className="mt-4 space-y-4">
            <div>
              <label className="label">创意描述 Prompt</label>
              <textarea
                className="input min-h-[104px] resize-none"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={
                  mode === "image"
                    ? "例如:未来感城市夜景,霓虹蓝光,电影质感,超高清"
                    : "例如:一只机械鲸鱼在星空中游动,慢镜头,科幻氛围"
                }
              />
            </div>

            {mode === "image" && (
              <div>
                <label className="label">排除内容 Negative</label>
                <input
                  className="input"
                  value={negative}
                  onChange={(e) => setNegative(e.target.value)}
                  placeholder="低质量, 模糊, 多余的手指…"
                />
              </div>
            )}

            <div>
              <label className="label">模型</label>
              <select className="input" value={model} onChange={(e) => setModel(e.target.value)}>
                {models
                  .filter((m) => m.type === mode)
                  .map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}{m.supports_4k ? " · ULA 4K" : ""}
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="label">画面比例</label>
              <div className="flex flex-wrap gap-2">
                {(mode === "image" ? IMAGE_RATIOS : VIDEO_RATIOS).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRatio(r)}
                    className={cn(
                      "rounded-md px-3 py-1.5 text-xs transition",
                      ratio === r
                        ? "bg-brand-500 text-white shadow-glow"
                        : "glass text-slate-300 hover:bg-white/10"
                    )}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            {mode === "image" ? (
              <div>
                <label className="label">生成数量:{numOutputs}</label>
                <input
                  type="range"
                  min={1}
                  max={4}
                  value={numOutputs}
                  onChange={(e) => setNumOutputs(Number(e.target.value))}
                  className="w-full accent-brand-500"
                />
              </div>
            ) : (
              <div>
                <label className="label">时长:{duration}s</label>
                <input
                  type="range"
                  min={2}
                  max={15}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="w-full accent-brand-500"
                />
              </div>
            )}

            <button onClick={generate} disabled={busy} className="btn-primary w-full">
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  生成中…
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" />
                  开始生成
                </>
              )}
            </button>

            {quota && <QuotaBar quota={quota} mode={mode} />}
          </div>
        </div>

        {/* 预览区 */}
        <div className="card min-h-[440px] p-4">
          <ResultArea mode={mode} state={state} />
        </div>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div>
      <div className="mb-1 inline-flex items-center gap-2 text-xs text-brand-300">
        <Sparkles className="h-3.5 w-3.5" /> AIGC 创作工作台
      </div>
      <h1 className="page-title">开始你的创作</h1>
      <p className="page-sub">
        输入创意描述,选择参数,实时查看生成进度与结果。
      </p>
    </div>
  );
}

function ModeSwitch({ mode, setMode }: { mode: Mode; setMode: (m: Mode) => void }) {
  return (
    <div className="flex rounded-md bg-ink-900/60 p-1">
      {([
        { id: "image", label: "出图", icon: ImageIcon },
        { id: "video", label: "出视频", icon: Film },
      ] as const).map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id)}
          className={cn(
            "flex flex-1 items-center justify-center gap-2 rounded py-2 text-[13px] transition",
            mode === m.id
              ? "bg-gradient-to-r from-brand-500 to-cyanx-500 text-white shadow-glow"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          <m.icon className="h-4 w-4" />
          {m.label}
        </button>
      ))}
    </div>
  );
}

function QuotaBar({ quota, mode }: { quota: QuotaUsage; mode: Mode }) {
  const used = mode === "image" ? quota.daily_image_used : quota.daily_video_used;
  const total = mode === "image" ? quota.daily_image_quota : quota.daily_video_quota;
  const pct = total ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div className="rounded-md bg-ink-900/40 p-3">
      <div className="mb-1.5 flex justify-between text-xs text-slate-400">
        <span>今日{mode === "image" ? "出图" : "出视频"}额度</span>
        <span className="text-slate-300">
          {used} / {total}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-cyanx-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  idle: "等待创作",
  queued: "排队中",
  running: "生成中",
  succeeded: "生成完成",
  failed: "生成失败",
  cancelled: "已取消",
};

function ResultArea({ mode, state }: { mode: Mode; state: ReturnType<typeof useTaskProgress>["state"] }) {
  const isBusy = state.status === "queued" || state.status === "running";

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-[13px] text-slate-300">预览</span>
        <span
          className={cn(
            "rounded px-2.5 py-1 text-xs",
            state.status === "succeeded" && "bg-emerald-500/15 text-emerald-300",
            state.status === "failed" && "bg-red-500/15 text-red-300",
            isBusy && "bg-brand-500/15 text-brand-300",
            state.status === "idle" && "bg-white/5 text-slate-400"
          )}
        >
          {STATUS_LABEL[state.status]}
        </span>
      </div>

      {isBusy && (
        <div className="mb-4">
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-cyanx-500"
              animate={{ width: `${Math.max(8, state.progress)}%` }}
              transition={{ ease: "easeOut" }}
            />
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {state.progress}% · {mode === "video" ? "出视频通常需要较长时间,请耐心等待" : "正在生成高清画面"}
          </div>
        </div>
      )}

      <div className="flex flex-1 items-center justify-center">
        <AnimatePresence mode="wait">
          {state.status === "idle" && (
            <Placeholder key="idle" />
          )}

          {isBusy && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid w-full grid-cols-2 gap-4"
            >
              {Array.from({ length: mode === "image" ? 2 : 1 }).map((_, i) => (
                <div
                  key={i}
                  className="relative aspect-square overflow-hidden rounded-md bg-ink-900/60"
                >
                  <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                </div>
              ))}
            </motion.div>
          )}

          {state.status === "succeeded" && (
            <motion.div
              key="result"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              className="grid w-full gap-4 sm:grid-cols-2"
            >
              {state.outputs.map((o, i) => (
                <OutputCard key={i} url={o.url} type={o.type} />
              ))}
            </motion.div>
          )}

          {state.status === "failed" && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center"
            >
              <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-red-500/15 text-red-300">
                !
              </div>
              <p className="text-sm text-slate-300">生成失败</p>
              <p className="mt-1 max-w-sm text-xs text-slate-500">{state.error}</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function Placeholder() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="text-center"
    >
      <div className="mx-auto mb-4 grid h-14 w-14 animate-floaty place-items-center rounded-md bg-gradient-to-br from-brand-500/20 to-cyanx-500/10 text-brand-300">
        <Sparkles className="h-6 w-6" />
      </div>
      <p className="text-sm text-slate-400">填写创意描述,点击「开始生成」</p>
    </motion.div>
  );
}

function OutputCard({ url, type }: { url: string; type: string }) {
  return (
    <div className="group relative overflow-hidden rounded-md border border-white/10 bg-ink-900/60">
      {type === "video" ? (
        <video src={url} controls className="w-full" />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="生成结果" className="w-full object-cover" />
      )}
      <a
        href={url}
        download
        target="_blank"
        rel="noreferrer"
        className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-md bg-black/50 text-white opacity-0 backdrop-blur transition group-hover:opacity-100"
      >
        <Download className="h-4 w-4" />
      </a>
    </div>
  );
}
