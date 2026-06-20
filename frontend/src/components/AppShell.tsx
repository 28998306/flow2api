"use client";

import {
  ClipboardList,
  Film,
  History,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Settings,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { clearTokens, getMe, getToken, type Me } from "@/lib/api";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/workbench", label: "创作工作台", icon: Sparkles },
  { href: "/history", label: "我的作品", icon: History },
];

const adminItems = [
  { href: "/admin", label: "数据概览", icon: LayoutDashboard },
  { href: "/admin/logs", label: "任务日志", icon: ClipboardList },
  { href: "/admin/accounts", label: "账号池", icon: Film },
  { href: "/admin/api-keys", label: "下游 Key", icon: KeyRound },
  { href: "/admin/users", label: "用户与额度", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    getMe()
      .then(setMe)
      .catch(() => {
        clearTokens();
        router.replace("/");
      });
  }, [router]);

  function logout() {
    clearTokens();
    router.replace("/");
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-white/[0.06] bg-ink-950/60 p-4 backdrop-blur-xl lg:flex">
        <div className="px-1 py-1">
          <Logo />
        </div>

        <nav className="mt-6 flex-1 space-y-0.5">
          <p className="px-3 pb-1.5 text-[10px] uppercase tracking-widest text-slate-500">
            创作
          </p>
          {navItems.map((item) => (
            <NavLink key={item.href} {...item} active={pathname === item.href} />
          ))}

          {me?.role === "admin" && (
            <>
              <p className="px-3 pb-1.5 pt-5 text-[10px] uppercase tracking-widest text-slate-500">
                管理后台
              </p>
              {adminItems.map((item) => (
                <NavLink
                  key={item.href}
                  {...item}
                  active={pathname === item.href}
                />
              ))}
            </>
          )}
        </nav>

        <div className="mt-auto">
          <div className="glass mb-2 flex items-center gap-2.5 rounded-md p-2.5">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-cyanx-500 text-xs text-white">
              {me?.email?.[0]?.toUpperCase() ?? "U"}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] text-white">
                {me?.full_name || me?.email || "—"}
              </div>
              <div className="truncate text-xs text-slate-400">
                {me?.role === "admin" ? "管理员" : "创作者"}
              </div>
            </div>
          </div>
          <button onClick={logout} className="btn-ghost w-full">
            <LogOut className="h-4 w-4" />
            退出登录
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 lg:hidden">
          <Logo />
          <button onClick={logout} className="btn-ghost btn-sm">
            <LogOut className="h-4 w-4" />
          </button>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition",
        active
          ? "bg-gradient-to-r from-brand-500/20 to-cyanx-500/10 text-white shadow-[inset_0_0_0_1px_rgba(76,130,247,0.3)]"
          : "text-slate-400 hover:bg-white/[0.05] hover:text-slate-200"
      )}
    >
      <Icon className={cn("h-4 w-4", active && "text-brand-300")} />
      {label}
    </Link>
  );
}
