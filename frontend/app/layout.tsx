import type { Metadata } from "next";
import "./globals.css";
import { MotionProvider } from "@/components/MotionProvider";

export const metadata: Metadata = {
  title: "AI Recruiter Email & Cover Letter Generator for Students",
  description:
    "Generate personalized, verified, and hallucination-free recruiter emails and cover letters from your own student profile.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0A1128] text-[#F1F5F9] antialiased selection:bg-[#FF6A3D] selection:text-white">
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}

