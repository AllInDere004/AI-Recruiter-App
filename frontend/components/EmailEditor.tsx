"use client";

import React, { useState } from "react";
import {
  Copy,
  ExternalLink,
  RotateCw,
  Check,
  AlertTriangle,
  Eye,
  FileEdit,
  Sparkles,
} from "lucide-react";

import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Badge } from "./ui/badge";
import { countWords } from "@/lib/utils";

interface EmailEditorProps {
  subject: string;
  body: string;
  version?: number;
  tone: string;
  verifiedSkills?: string[];
  verifiedProjects?: string[];
  warnings?: string[];
  onSubjectChange: (sub: string) => void;
  onBodyChange: (body: string) => void;
  onRegenerate: (newTone?: string) => Promise<void>;
  isRegenerating?: boolean;
}

export function EmailEditor({
  subject,
  body,
  version = 1,
  tone,
  verifiedSkills = [],
  verifiedProjects = [],
  warnings = [],
  onSubjectChange,
  onBodyChange,
  onRegenerate,
  isRegenerating = false,
}: EmailEditorProps) {
  const [copied, setCopied] = useState(false);
  const [showEvidenceHighlights, setShowEvidenceHighlights] = useState(true);

  const wordCount = countWords(body);

  const handleCopy = () => {
    const fullText = `Subject: ${subject}\n\n${body}`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleOpenMailto = () => {
    const mailtoUrl = `mailto:?subject=${encodeURIComponent(
      subject
    )}&body=${encodeURIComponent(body)}`;
    window.open(mailtoUrl, "_blank");
  };

  // Render highlighted evidence in read-only / preview mode
  const renderHighlightedBody = () => {
    if (!showEvidenceHighlights) {
      return <div className="whitespace-pre-wrap font-sans text-sm">{body}</div>;
    }

    const tokensToHighlight = [
      ...verifiedSkills.map((s) => ({ text: s, type: "skill" })),
      ...verifiedProjects.map((p) => ({ text: p, type: "project" })),
    ].filter((item) => item.text.trim().length > 0);

    if (tokensToHighlight.length === 0) {
      return <div className="whitespace-pre-wrap font-sans text-sm">{body}</div>;
    }

    // Build regex pattern matching verified skills or projects
    const pattern = new RegExp(
      `(${tokensToHighlight
        .map((t) => t.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|")})`,
      "gi"
    );

    const parts = body.split(pattern);

    return (
      <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[#F1F5F9]">
        {parts.map((part, index) => {
          const matched = tokensToHighlight.find(
            (t) => t.text.toLowerCase() === part.toLowerCase()
          );
          if (matched) {
            return (
              <span
                key={index}
                className={
                  matched.type === "skill"
                    ? "bg-[#FF6A3D]/20 text-[#FF8C38] px-1 py-0.5 rounded font-medium border border-[#FF6A3D]/40"
                    : "bg-[#FFEADB]/20 text-[#FFD6A4] px-1 py-0.5 rounded font-medium border border-[#FFEADB]/30"
                }
                title={`Verified from profile: ${matched.type}`}
              >
                {part}
              </span>
            );
          }
          return <span key={index}>{part}</span>;
        })}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Hallucination / Fact Verification Banner */}
      {warnings.length > 0 && <div role="alert" className="p-4 border border-amber-700 rounded-xl text-amber-300"><p className="font-semibold">Unverified claims to review</p>{warnings.map((warning,index) => <p className="text-sm mt-2" key={index}>{warning}</p>)}</div>}

      {/* Editor Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 pb-2 border-b border-[#1E3560]">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs border-[#1E3560] text-[#8FA0BE]">
            Saved draft
          </Badge>
          <Badge variant="secondary" className="capitalize text-xs bg-[#152449] text-[#FF8C38] border border-[#1E3560]">
            Tone: {tone}
          </Badge>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              wordCount >= 150 && wordCount <= 250
                ? "bg-[#FF6A3D]/15 text-[#FF8C38] border border-[#FF6A3D]/30"
                : "bg-[#152449] text-[#8FA0BE] border border-[#1E3560]"
            }`}
          >
            {wordCount} words (target: 150-250)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowEvidenceHighlights(!showEvidenceHighlights)}
            className={`text-xs flex items-center gap-1 px-2.5 py-1.5 rounded-lg border transition-colors ${
              showEvidenceHighlights
                ? "bg-[#FF6A3D]/15 border-[#FF6A3D]/30 text-[#FF8C38] font-medium"
                : "border-[#1E3560] text-[#8FA0BE] hover:bg-[#152449]"
            }`}
          >
            <Eye className="h-3.5 w-3.5 text-[#FF6A3D]" />
            {showEvidenceHighlights ? "Evidence Visible" : "Raw View"}
          </button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onRegenerate()}
            isLoading={isRegenerating}
            title="Regenerate email using prompt pipeline"
            className="border-[#1E3560] bg-[#101C38] text-[#F1F5F9] hover:text-[#FF6A3D]"
          >
            <RotateCw className="h-3.5 w-3.5 mr-1 text-[#FF6A3D]" />
            Regenerate
          </Button>
        </div>
      </div>

      {/* Subject Line Input */}
      <div>
        <label className="block text-xs font-semibold text-[#8FA0BE] mb-1">
          Subject Line
        </label>
        <Input
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
          className="font-medium text-[#F1F5F9] bg-[#0E1B38] border-[#1E3560] focus-visible:ring-[#FF6A3D]"
          aria-label="Subject line"
          placeholder="Subject line..."
        />
      </div>

      {/* Email Body / Preview */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs font-semibold text-[#8FA0BE]">
            Email Body
          </label>
          {showEvidenceHighlights && (
            <div className="flex items-center gap-2 text-[11px] text-[#8FA0BE]">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-[#FF6A3D] inline-block" /> Profile Skills
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-[#FFD6A4] inline-block" /> Verified Projects
              </span>
            </div>
          )}
        </div>

        {showEvidenceHighlights ? (
          <div className="min-h-[280px] p-4 rounded-xl border border-[#1E3560] bg-[#0E1B38] overflow-y-auto">
            {renderHighlightedBody()}
          </div>
        ) : (
          <textarea
            value={body}
            onChange={(e) => onBodyChange(e.target.value)}
            rows={12}
            className="w-full text-sm rounded-xl border border-[#1E3560] bg-[#0E1B38] p-4 focus:outline-none focus:ring-2 focus:ring-[#FF6A3D] font-sans leading-relaxed text-[#F1F5F9]"
            aria-label="Email body"
            placeholder="Generated recruiter email..."
          />
        )}
      </div>

      {/* Action Buttons: Copy & Mailto */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-2">
          <Button onClick={handleCopy} variant="secondary" size="sm">
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 mr-1.5 text-emerald-400" /> Copied!
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 mr-1.5" /> Copy Email
              </>
            )}
          </Button>

          <Button onClick={handleOpenMailto} variant="outline" size="sm" className="border-[#1E3560] bg-[#101C38] text-[#F1F5F9] hover:text-[#FF6A3D]">
            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
            Open in Email App
          </Button>
        </div>

        <p className="text-[11px] text-[#8FA0BE] italic">
          Tip: You can edit the text directly at any time.
        </p>
      </div>
    </div>
  );
}
