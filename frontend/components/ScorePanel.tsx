"use client";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
export function ScorePanel({ score, edited = false }: { score: number | null; edited?: boolean }) {
  return <Card className="workspace-pearl"><CardHeader><CardTitle>Alignment score</CardTitle></CardHeader><CardContent className="space-y-3">
    <p className="text-3xl font-bold text-[#FF8C38]">{score === null || edited ? "Not scored" : `${score.toFixed(1)} / 100`}</p>
    <p className="text-xs text-[#8FA0BE]">{edited ? "The generated score and fact check do not describe your manual edits. Save your changes or regenerate for a new assessment." : "Calculated by the backend using semantic alignment and job phrase coverage. This is not a hiring probability."}</p>
  </CardContent></Card>;
}
