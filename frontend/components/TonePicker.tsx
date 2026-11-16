"use client";

import React from "react";
import { ToneKey, ToneOption } from "@/types";
import { Check } from "lucide-react";

export const TONE_OPTIONS: ToneOption[] = [
  {
    key: "concise", label: "Concise",
    description: "Brief, direct, and focused on relevant verified experience.",
    example: "I am interested in the role and would welcome a conversation.",
  },
  {
    key: "enthusiastic", label: "Enthusiastic",
    description: "Positive interest grounded in your actual skills and projects.",
    example: "I am excited to contribute my experience to this opportunity.",
  },
  {
    key: "professional",
    label: "Professional",
    description: "Traditional, polished, respectful corporate etiquette.",
    example: "Dear Hiring Team, I am submitting my credentials for your review...",
  },
  {
    key: "casual",
    label: "Casual",
    description: "Warm, personable, enthusiastic yet strictly professional.",
    example: "Hi Sarah, I loved your recent team blog on distributed systems...",
  },
  {
    key: "confident",
    label: "Confident",
    description: "Outcome-focused, assertive, leads with proof of work.",
    example: "I engineered our campus platform to 1.2k users and would love to bring this speed to Stripe...",
  },
  {
    key: "short",
    label: "Short & Crisp",
    description: "Under 120 words, hyper-scannable for busy senior engineering managers.",
    example: "Quick introduction: CS fresher with FastAPI/TS projects. 3 matching points attached...",
  },
];

interface TonePickerProps {
  selectedTone: ToneKey;
  onSelectTone: (tone: ToneKey) => void;
}

export function TonePicker({ selectedTone, onSelectTone }: TonePickerProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-semibold text-[#F1F5F9]">
          Select Tone of Voice
        </label>
        <span className="text-xs text-[#8FA0BE]">
          Calibrates vocabulary and sentence structure
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {TONE_OPTIONS.map((tone) => {
          const isSelected = selectedTone === tone.key;
          return (
            <div
              key={tone.key}
              onClick={() => onSelectTone(tone.key)}
              className={`workspace-choice p-3.5 rounded-xl border text-left cursor-pointer transition-all flex flex-col justify-between ${
                isSelected
                  ? "border-[#FF6A3D] bg-[#FF6A3D]/10 ring-2 ring-[#FF6A3D]/30 shadow-md shadow-[#FF6A3D]/15"
                  : "border-[#1E3560] hover:border-[#FF6A3D]/50 bg-[#101C38]"
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-sm text-[#F1F5F9]">
                    {tone.label}
                  </h4>
                  {isSelected && (
                    <span className="h-4 w-4 rounded-full bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white flex items-center justify-center font-bold">
                      <Check className="h-2.5 w-2.5" />
                    </span>
                  )}
                </div>
                <p className="text-xs text-[#8FA0BE] mt-1">
                  {tone.description}
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-[#1E3560]">
                <p className="text-[11px] text-[#8FA0BE]/80 italic line-clamp-2">
                  &ldquo;{tone.example}&rdquo;
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

