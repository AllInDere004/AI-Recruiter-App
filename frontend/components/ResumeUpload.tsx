"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Profile } from "@/types";
import { api } from "@/lib/api";

interface ResumeUploadProps {
  onParsed: (data: Profile) => void;
  isLoading?: boolean;
}

export function ResumeUpload({ onParsed, isLoading: parentLoading }: ResumeUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    setErrorMsg(null);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      processFile(file);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMsg(null);
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = async (file: File) => {
    if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
      setErrorMsg("Please upload a valid PDF document of your resume.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg("Resume file size exceeds 10MB limit.");
      return;
    }

    setSelectedFile(file);
    setIsProcessing(true);
    try {
      const extracted = await api.uploadResume(file);
      onParsed(extracted);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error extracting resume data. Please try again.";
      setSelectedFile(null);
      setErrorMsg(message);
    } finally {
      setIsProcessing(false);
    }
  };

  const isLoading = isProcessing || parentLoading;

  return (
    <Card className="border-dashed border-2 border-[#1E3560] bg-[#101C38] text-[#F1F5F9] transition-all hover:border-[#FF6A3D]/50">
      <CardContent className="p-8 text-center flex flex-col items-center justify-center">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileInput}
          accept="application/pdf"
          className="hidden"
          disabled={isLoading}
        />

        {isLoading ? (
          <div className="py-8 flex flex-col items-center space-y-4">
            <div className="relative">
              <div className="h-16 w-16 rounded-2xl bg-[#FF6A3D]/15 flex items-center justify-center text-[#FF6A3D] border border-[#FF6A3D]/30 shadow-md shadow-[#FF6A3D]/25">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-[#F1F5F9]">
                Parsing Resume with AI...
              </h4>
              <p className="text-xs text-[#8FA0BE] mt-1 max-w-sm">
                Extracting contact details, skills, education, and experience from your resume.
              </p>
            </div>
          </div>
        ) : selectedFile ? (
          <div className="py-4 flex flex-col items-center space-y-3">
            <div className="h-14 w-14 rounded-2xl bg-[#FF6A3D]/20 text-[#FF6A3D] border border-[#FF6A3D]/40 flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <div>
              <p className="font-semibold text-[#F1F5F9] flex items-center justify-center gap-1.5 text-sm">
                <FileText className="h-4 w-4 text-[#FF6A3D]" />
                {selectedFile.name}
              </p>
              <p className="text-xs text-[#8FA0BE] mt-0.5">
                {(selectedFile.size / 1024).toFixed(1)} KB • Successfully parsed
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="mt-2 text-xs border-[#1E3560] bg-[#0E1B38] text-[#F1F5F9] hover:text-[#FF6A3D]"
            >
              Upload a different PDF
            </Button>
          </div>
        ) : (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            className={`w-full py-6 flex flex-col items-center cursor-pointer rounded-xl transition-colors ${
              dragOver ? "bg-[#FF6A3D]/10 border border-[#FF6A3D]" : ""
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="h-16 w-16 rounded-2xl bg-[#FF6A3D]/15 text-[#FF6A3D] border border-[#FF6A3D]/30 flex items-center justify-center mb-4 shadow-md shadow-[#FF6A3D]/20 group-hover:scale-105 transition-transform">
              <UploadCloud className="h-8 w-8" />
            </div>

            <h4 className="font-semibold text-[#F1F5F9] text-base">
              Drop your resume PDF here, or <span className="text-[#FF6A3D] hover:text-[#FFA270] underline">browse</span>
            </h4>
            <p className="text-xs text-[#8FA0BE] mt-1.5 max-w-sm">
              We extract your skills, education, and experience for you to review.
            </p>

            <div className="mt-4 flex items-center gap-2 text-[11px] text-[#8FA0BE]">
              <span className="bg-[#0E1B38] text-[#8FA0BE] px-2.5 py-1 rounded-full border border-[#1E3560]">
                PDF only
              </span>
              <span className="bg-[#0E1B38] text-[#8FA0BE] px-2.5 py-1 rounded-full border border-[#1E3560]">
                Max 10MB
              </span>
            </div>
          </div>
        )}

        {errorMsg && (
          <div className="mt-4 flex items-center gap-2 text-xs text-rose-300 bg-rose-500/15 px-3.5 py-2 rounded-lg border border-rose-500/30">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
