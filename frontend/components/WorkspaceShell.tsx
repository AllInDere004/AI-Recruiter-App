"use client";

import Link from "next/link";
import { ChevronRight, LayoutDashboard, Sparkles, UserRound } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { DashboardAtmosphere } from "@/components/DashboardAtmosphere";
import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

/** The dashboard's visual shell shared by the four working pages. */
export function WorkspaceShell({ section, children }: { section: string; children: ReactNode }) {
  const { user,isLoading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!isLoading && !user) router.replace("/login"); },[user,isLoading,router]);
  if (isLoading || !user) return <main className="min-h-screen grid place-items-center bg-[#0A1128]">Restoring your session...</main>;
  return (
    <div className="recruiter-dashboard recruiter-workspace flex min-h-screen flex-col lg:flex-row">
      <DashboardAtmosphere />
      <Sidebar />
      <div className="workspace-content min-w-0 flex-1">
        <header className="workspace-toolbar flex items-center justify-between gap-3 px-4 pt-5 sm:px-6 lg:px-8">
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-xs text-[#B6C6E4]">
            <Link href="/dashboard" className="flex items-center gap-2 hover:text-white"><LayoutDashboard className="h-3.5 w-3.5" /><span className="hidden sm:inline">Workspace</span></Link>
            <ChevronRight className="h-3 w-3 shrink-0 opacity-50" /><span className="truncate text-[#F1F5F9]">{section}</span>
          </nav>
          <div className="flex items-center gap-3 shrink-0">
            <span className="hidden sm:flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[#F7C9A8]"><Sparkles className="h-3 w-3" /> Your next chapter</span>
            <Link href="/profile" aria-label="Open profile" className="dashboard-avatar"><UserRound className="h-4 w-4" /></Link>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
