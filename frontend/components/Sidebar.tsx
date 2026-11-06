"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot, ArrowRight, Sparkles,
  LayoutDashboard,
  MailPlus,
  KanbanSquare,
  UserCheck,
  Settings,
  LogOut,
  Moon,
  Sun,
  Menu,
  X,
  GraduationCap,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isDark, setIsDark] = useState(false);

  // Toggle dark mode class on documentElement
  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    if (typeof document !== "undefined") {
      if (nextDark) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    }
  };

  const navItems = [
    {
      label: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "New Email",
      href: "/new-email",
      icon: MailPlus,
      highlight: true,
    },
    {
      label: "Application Tracker",
      href: "/tracker",
      icon: KanbanSquare,
    },
    {
      label: "Profile",
      href: "/profile",
      icon: UserCheck,
    },
    {
      label: "Settings",
      href: "/settings",
      icon: Settings,
    },
  ];

  return (
    <>
      {/* Mobile Top Header */}
      <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-[#0E1B38] border-b border-[#1E3560] sticky top-0 z-40">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] flex items-center justify-center text-white font-bold shadow-md shadow-[#FF6A3D]/30">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <span className="font-bold text-sm tracking-tight text-[#F1F5F9]">
              AI Recruiter
            </span>
            <span className="ml-1.5 text-[10px] font-semibold uppercase bg-[#FF6A3D]/15 text-[#FF8C38] border border-[#FF6A3D]/30 px-1.5 py-0.5 rounded-full">
              Career
            </span>
          </div>
        </div>

        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-lg text-[#8FA0BE] hover:bg-[#152449] hover:text-[#F1F5F9]"
          aria-label="Toggle Menu"
        >
          {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </header>

      {/* Mobile Dropdown Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 top-[57px] bg-[#0A1128]/90 backdrop-blur-md z-50 flex flex-col justify-between">
          <div className="bg-[#0E1B38] p-4 border-b border-[#1E3560] space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    "flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors",
                    isActive
                      ? "bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white font-bold shadow-md shadow-[#FF6A3D]/30"
                      : "text-[#8FA0BE] hover:bg-[#152449] hover:text-[#F1F5F9]"
                  )}
                >
                  <Icon className={cn("h-5 w-5", isActive ? "text-white" : "text-[#8FA0BE]")} />
                  {item.label}
                </Link>
              );
            })}

            <div className="pt-4 border-t border-[#1E3560] flex items-center justify-between">
              <button
                onClick={toggleTheme}
                className="flex items-center gap-2 text-sm text-[#8FA0BE] hover:text-[#F1F5F9] p-2 rounded-lg"
              >
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                {isDark ? "Light Mode" : "Dark Mode"}
              </button>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 text-sm text-rose-400 hover:text-rose-300 p-2"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Left Sidebar */}
      <aside className="recruiter-sidebar hidden lg:flex shrink-0 flex-col justify-between w-64 border-r border-[#1E3560] bg-[#0E1B38] min-h-screen p-5 sticky top-0 h-screen overflow-y-auto">
        <div className="space-y-6">
          {/* Logo & Brand */}
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] flex items-center justify-center text-white font-bold shadow-lg shadow-[#FF6A3D]/30 group-hover:scale-105 transition-transform">
              <Bot className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-[#F1F5F9] tracking-tight">
                  AI Recruiter
                </span>
                <span className="text-[10px] font-semibold bg-[#FF6A3D]/15 text-[#FF8C38] border border-[#FF6A3D]/30 px-1.5 py-0.5 rounded-full">
                  v1.0
                </span>
              </div>
              <p className="text-xs text-[#8FA0BE] flex items-center gap-1">
                <UserCheck className="h-3 w-3 text-[#FF6A3D]" /> For Job Seekers & Professionals
              </p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="space-y-1.5 pt-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150",
                    isActive
                      ? "bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white font-bold shadow-md shadow-[#FF6A3D]/30"
                      : "text-[#8FA0BE] hover:bg-[#152449] hover:text-[#F1F5F9]"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={cn("h-4 w-4", isActive ? "text-white" : "text-[#8FA0BE]")} />
                    <span>{item.label}</span>
                  </div>
                  {item.highlight && !isActive && (
                    <span className="text-[10px] font-semibold bg-[#FF6A3D]/15 text-[#FF8C38] px-2 py-0.5 rounded-full border border-[#FF6A3D]/30">
                      Gen
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        <Link href="/profile" className="sidebar-toolkit mt-auto mb-6 block rounded-2xl p-4 border border-orange-300/20 bg-orange-400/10 hover:bg-orange-400/15 transition-colors">
          <Sparkles className="h-6 w-6 text-orange-300 mb-2" />
          <p className="text-sm font-bold text-white">Your career, upgraded</p>
          <p className="text-xs leading-relaxed text-[#BAC7DE] mt-2">A stronger profile. Better outreach. Your next big opportunity.</p>
          <span className="mt-4 flex items-center justify-between rounded-lg bg-gradient-to-r from-orange-400 to-orange-500 px-3 py-2 text-xs font-bold text-white">Complete your profile <ArrowRight className="h-3 w-3" /></span>
        </Link>
        {/* Footer & User Card */}
        <div className="pt-6 border-t border-[#1E3560] space-y-4">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs text-[#8FA0BE] font-medium">Appearance</span>
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg border border-[#1E3560] text-[#8FA0BE] hover:bg-[#152449] hover:text-[#F1F5F9] transition-colors"
              title="Toggle theme"
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>

          <div className="flex items-center justify-between bg-[#101C38] p-3 rounded-xl border border-[#1E3560]">
            <div className="truncate pr-2">
              <p className="text-xs font-semibold text-[#F1F5F9] truncate">
                {user?.email || "Your account"}
              </p>
              <p className="text-[11px] text-[#8FA0BE] truncate">
                {user?.email || "student@university.edu"}
              </p>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="p-1.5 rounded-lg text-[#8FA0BE] hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

