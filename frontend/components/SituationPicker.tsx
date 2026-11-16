"use client";

import React from "react";
import {
  Send,
  Mail,
  Clock,
  HeartHandshake,
  Users,
  Sparkles,
  MessageSquare,
  Check,
} from "lucide-react";
import { SituationKey, SituationOption } from "@/types";
import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";

export const SITUATION_OPTIONS: SituationOption[] = [
  {
    key: "internship", title: "Internship application",
    description: "Connect verified coursework, skills, and projects to an internship.",
    badge: "Student opportunities", iconName: "Sparkles",
  },
  {
    key: "apply",
    title: "1. Apply for a Job",
    description: "Standard application email + concise cover letter highlighting verified project evidence.",
    badge: "Most Popular",
    iconName: "Send",
  },
  {
    key: "cold_email",
    title: "2. Cold Email to Recruiter",
    description: "Proactive outreach when no public role is open. Hooks interest with relevant proof of work.",
    badge: "High Response",
    iconName: "Mail",
  },
  {
    key: "follow_up",
    title: "3. Follow-up After Applying",
    description: "Polite check-in 5 to 7 days after application. Adds an update on project progress.",
    badge: "Follow-up Due",
    iconName: "Clock",
  },
  {
    key: "thank_you",
    title: "4. Thank-You After Interview",
    description: "Post-interview note expressing gratitude and connecting interview points to your skills.",
    badge: "Interview Stage",
    iconName: "HeartHandshake",
  },
  {
    key: "referral",
    title: "5. Referral Request",
    description: "Thoughtful note to an alumnus, connection, or employee asking for an internal referral.",
    badge: "Networking",
    iconName: "Users",
  },
  {
    key: "reply_recruiter",
    title: "6. Reply to Recruiter Inbound",
    description: "Direct response confirming interest, availability, salary expectations, and scheduling times.",
    badge: "Active Chat",
    iconName: "MessageSquareCheck",
  },
];

interface SituationPickerProps {
  selectedSituation: SituationKey;
  onSelectSituation: (key: SituationKey) => void;
}

export function SituationPicker({
  selectedSituation,
  onSelectSituation,
}: SituationPickerProps) {
  const getIcon = (name: string) => {
    switch (name) {
      case "Send":
        return <Send className="h-4 w-4" />;
      case "Mail":
        return <Mail className="h-4 w-4" />;
      case "Clock":
        return <Clock className="h-4 w-4" />;
      case "HeartHandshake":
        return <HeartHandshake className="h-4 w-4" />;
      case "Users":
        return <Users className="h-4 w-4" />;
      case "Sparkles":
        return <Sparkles className="h-4 w-4" />;
      case "MessageSquare":
      case "MessageSquareCheck":
        return <MessageSquare className="h-4 w-4" />;
      default:
        return <Mail className="h-4 w-4" />;
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-semibold text-[#F1F5F9]">
          Select Situation / Outreach Goal
        </label>
        <span className="text-xs text-[#8FA0BE]">
          6 situation templates
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {SITUATION_OPTIONS.map((sit) => {
          const isSelected = selectedSituation === sit.key;
          return (
            <div
              key={sit.key}
              onClick={() => onSelectSituation(sit.key)}
              className={`workspace-choice p-4 rounded-xl border text-left cursor-pointer transition-all relative ${
                isSelected
                  ? "border-[#FF6A3D] bg-[#FF6A3D]/10 ring-2 ring-[#FF6A3D]/30 shadow-md shadow-[#FF6A3D]/15"
                  : "border-[#1E3560] hover:border-[#FF6A3D]/50 bg-[#101C38]"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`h-8 w-8 rounded-lg flex items-center justify-center ${
                      isSelected
                        ? "bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white font-bold shadow-sm"
                        : "bg-[#152449] text-[#8FA0BE]"
                    }`}
                  >
                    {getIcon(sit.iconName)}
                  </div>
                  <div>
                    <h4 className="font-semibold text-sm text-[#F1F5F9]">
                      {sit.title}
                    </h4>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <Badge variant={isSelected ? "default" : "secondary"} className="text-[10px]">
                    {sit.badge}
                  </Badge>
                  {isSelected && (
                    <span className="h-4 w-4 rounded-full bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white flex items-center justify-center text-[10px] font-bold">
                      <Check className="h-2.5 w-2.5" />
                    </span>
                  )}
                </div>
              </div>

              <p className="text-xs text-[#8FA0BE] mt-2 line-clamp-2 pl-10">
                {sit.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

