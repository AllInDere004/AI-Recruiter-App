"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";

export default function GmailCallbackPage(){const [status,setStatus]=useState("Completing secure Gmail connection...");useEffect(()=>{const query=new URLSearchParams(window.location.search);const state=query.get("state"),code=query.get("code");if(!state||!code){setStatus("Google did not return a valid authorization response.");return;}void api.finishGmailOAuth(state,code).then(()=>setStatus("Gmail connected. Return to settings to review approved drafts.")).catch(cause=>setStatus(cause instanceof ApiError?cause.message:"Gmail connection failed."));},[]);return <main className="min-h-screen grid place-items-center bg-[#0A1128] p-6"><div className="max-w-lg rounded-2xl border border-[#1E3560] bg-[#101C38] p-8"><h1 className="text-2xl font-bold">Gmail connection</h1><p role="status" className="my-4">{status}</p><Link href="/settings" className="text-[#FF8C38]">Return to settings</Link></div></main>}
