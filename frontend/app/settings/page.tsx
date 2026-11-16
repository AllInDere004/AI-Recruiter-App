"use client";
import { useAuth } from "@/hooks/useAuth";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { IntegrationSettings } from "@/components/IntegrationSettings";
export default function SettingsPage() {
  const { user,logout } = useAuth();
  return <WorkspaceShell section="Settings"><main className="workspace-main p-4 sm:p-8 space-y-6 max-w-4xl mx-auto"><h1 className="text-3xl font-bold">Account settings</h1><Card className="workspace-pearl"><CardHeader><CardTitle>Your account</CardTitle></CardHeader><CardContent className="space-y-3"><p>{user?.email || "Loading account..."}</p><p className="text-sm text-[#8FA0BE]">Profile details are managed on the profile page. AI requests use the model configured by your backend.</p><Button onClick={logout}>Sign out</Button></CardContent></Card><IntegrationSettings/></main></WorkspaceShell>;
}
