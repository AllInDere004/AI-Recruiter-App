"use client";
import type { MatchResponse } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
export function MatchPoints({ match, isLoading = false }: { match: MatchResponse | null; isLoading?: boolean }) {
  return <Card className="workspace-pearl"><CardHeader><CardTitle>Resume and job match</CardTitle></CardHeader><CardContent className="space-y-4">
    {isLoading ? <p role="status">Computing semantic match...</p> : match ? <><p className="text-3xl font-bold text-[#FF8C38]">{match.overall_score.toFixed(1)} / 100</p><p className="text-sm">{match.summary}</p><div><h3 className="font-semibold text-sm">Matched skills</h3><p className="text-sm text-emerald-300">{match.matched_skills.join(", ") || "No required skills matched."}</p></div><div><h3 className="font-semibold text-sm">Missing skills</h3><p className="text-sm text-amber-300">{match.missing_skills.join(", ") || "No missing skills listed."}</p></div></> : <p>Select a job to compare it with your resume.</p>}
  </CardContent></Card>;
}
