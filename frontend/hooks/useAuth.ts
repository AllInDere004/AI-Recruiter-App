"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { User } from "@/types";
import { api, clearAuth, getToken, setToken } from "@/lib/api";

export function useAuth() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const fetchUser = useCallback(async () => {
    if (!getToken()) { setUser(null); setIsLoading(false); return null; }
    try { const me = await api.getMe(); setUser(me); return me; }
    catch { setUser(null); return null; }
    finally { setIsLoading(false); }
  }, []);
  useEffect(() => {
    void fetchUser();
    const refresh = () => { void fetchUser(); };
    window.addEventListener("auth-changed", refresh);
    window.addEventListener("storage", refresh);
    return () => { window.removeEventListener("auth-changed", refresh); window.removeEventListener("storage", refresh); };
  }, [fetchUser]);
  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const token = await api.login(email, password);
      setToken(token.access_token);
      const me = await api.getMe(); setUser(me); return me;
    } finally { setIsLoading(false); }
  };
  const signup = async (email: string, password: string) => {
    setIsLoading(true);
    try { const registered = await api.register(email, password); router.push(`/login?registered=1&email=${encodeURIComponent(email)}`); return registered; }
    finally { setIsLoading(false); }
  };
  const logout = () => { clearAuth(); setUser(null); router.replace("/login"); };
  return { user, isLoading, isAuthenticated: !!user, login, signup, fetchUser, logout };
}
