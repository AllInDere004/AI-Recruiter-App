import Link from "next/link";
import { HomepageMotion } from "@/components/HomepageMotion";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Cpu,
  Mail,
  KanbanSquare,
  CheckCircle2,
  GraduationCap,
  FileCheck,
  Clock,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <HomepageMotion>
    <div className="min-h-screen flex flex-col bg-[#0A1128] text-[#F1F5F9]">
      {/* Navigation */}
      <header data-home-nav className="border-b border-[#1E3560] bg-[#0E1B38]/90 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] flex items-center justify-center text-white font-bold shadow-md shadow-[#FF6A3D]/30">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="font-bold text-lg text-[#F1F5F9] tracking-tight">
                AI Recruiter
              </span>
              <span className="ml-2 text-xs font-semibold bg-[#FF6A3D]/15 text-[#FF8C38] border border-[#FF6A3D]/30 px-2 py-0.5 rounded-full">
                For Students & Freshers
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm" className="text-[#8FA0BE] hover:text-[#F1F5F9] hover:bg-[#152449]">
                Log In
              </Button>
            </Link>
            <Link href="/signup">
              <Button data-home-cta size="sm" className="bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white hover:from-[#F05526] hover:to-[#FF7A28] font-bold shadow-md shadow-[#FF6A3D]/30 border-0">
                Get Started Free <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section data-hero-copy className="relative pt-16 pb-20 overflow-hidden text-center max-w-5xl mx-auto px-4 sm:px-6">
          {/* Subtle Solar Ember Glow Backdrop */}
          <div data-home-glow aria-hidden="true" className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[350px] bg-[#FF6A3D]/10 rounded-full blur-[130px] pointer-events-none" />

          <div data-home-badge className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#FF6A3D]/15 border border-[#FF6A3D]/30 text-[#FF8C38] text-xs font-semibold mb-6 relative z-10">
            <GraduationCap className="h-4 w-4 text-[#FF6A3D]" /> Tailored for Students, Freshers & Career Switchers
          </div>

          <h1 data-home-heading className="text-4xl sm:text-6xl font-extrabold tracking-tight text-[#F1F5F9] leading-[1.15] relative z-10">
            {"Land recruiter interviews with".split(" ").map((word, index) => <span key={index}><span data-home-word>{word}</span>{" "}</span>)}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FF6A3D] via-[#FFA270] to-[#FFEADB]">
              {"verified proof of work".split(" ").map((word, index) => <span key={index}>{index > 0 ? " " : ""}<span data-home-word>{word}</span></span>)}
            </span>
            , {"not empty clichés.".split(" ").map((word, index) => <span key={index}>{index > 0 ? " " : ""}<span data-home-word>{word}</span></span>)}
          </h1>

          <p data-home-description className="mt-6 text-lg sm:text-xl text-[#8FA0BE] max-w-3xl mx-auto leading-relaxed relative z-10">
            Upload your resume once. Our ML matching engine pairs your verified projects and skills
            with real job needs, writes personalized outreach emails, checks for hallucinations, and scores draft quality.
          </p>

          <div data-home-actions className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5 relative z-10">
            <Link href="/signup" className="w-full sm:w-auto">
              <Button data-home-cta size="lg" className="w-full sm:w-auto font-bold bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] text-white hover:from-[#F05526] hover:to-[#FF7A28] shadow-lg shadow-[#FF6A3D]/30 border-0">
                Generate Your First Recruiter Email <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/dashboard" className="w-full sm:w-auto">
              <Button variant="outline" size="lg" className="w-full sm:w-auto border-[#1E3560] bg-[#101C38] text-[#F1F5F9] hover:bg-[#152449] hover:text-[#FF6A3D]">
                Explore Demo Dashboard
              </Button>
            </Link>
          </div>

          <div data-home-trust className="mt-8 flex flex-wrap items-center justify-center gap-6 text-xs text-[#8FA0BE] relative z-10">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-[#FF6A3D]" /> Zero invented facts
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-[#FF6A3D]" /> 7 specialized situations
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-[#FF6A3D]" /> Automated follow-up alerts
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-[#FF6A3D]" /> 100% Privacy & Data Deletion
            </span>
          </div>
          <div data-home-preview className="workflow-preview" aria-label="How AI Recruiter works">
            <div className="flex items-center justify-between gap-4 mb-5">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8FA0BE]">Your next opportunity starts here</span>
              <Sparkles className="h-4 w-4 text-[#FF8C38] shrink-0" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div data-float className="workflow-step">
                <FileCheck className="h-5 w-5 text-[#FF8C38] mb-3" />
                <p className="text-xs text-[#8FA0BE] mb-1">01 / YOUR STORY</p>
                <p className="text-sm font-semibold">Verified profile</p>
                <div className="mt-3 h-1 rounded-full bg-[#FF6A3D]/60" />
              </div>
              <div data-float className="workflow-step">
                <Cpu className="h-5 w-5 text-sky-400 mb-3" />
                <p className="text-xs text-[#8FA0BE] mb-1">02 / THE CONNECTION</p>
                <p className="text-sm font-semibold">Skills meet opportunity</p>
                <div className="mt-3 h-1 rounded-full bg-sky-400/60" />
              </div>
              <div data-float className="workflow-step">
                <Mail className="h-5 w-5 text-emerald-400 mb-3" />
                <p className="text-xs text-[#8FA0BE] mb-1">03 / YOUR NEXT MOVE</p>
                <p className="text-sm font-semibold">Personalized outreach</p>
                <div className="mt-3 h-1 rounded-full bg-emerald-400/60" />
              </div>
            </div>
            <p className="mt-5 text-xs text-[#8FA0BE] flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#FF8C38]" /> Built on your experience. Written for your future.</p>
          </div>
        </section>

        {/* Feature Grid */}
        <section className="py-16 bg-[#0E1B38] border-t border-[#1E3560]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div data-home-feature-heading className="text-center max-w-2xl mx-auto mb-12">
              <h2 className="text-2xl sm:text-3xl font-bold text-[#F1F5F9]">
                Engineered for Student Job Hunting
              </h2>
              <p className="text-sm text-[#8FA0BE] mt-2">
                Traditional AI tools hallucinate years of experience you do not have. Our pipeline grounds every sentence in your verified student profile.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Feature 1 */}
              <div data-home-feature className="p-6 rounded-2xl border border-[#1E3560] bg-[#101C38] space-y-3 hover:border-[#FF6A3D]/50 transition-colors shadow-lg">
                <div className="h-12 w-12 rounded-xl bg-[#FF6A3D]/15 text-[#FF6A3D] border border-[#FF6A3D]/30 flex items-center justify-center shadow-inner">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <h3 className="font-semibold text-lg text-[#F1F5F9]">
                  Strict Zero-Hallucination
                </h3>
                <p className="text-sm text-[#8FA0BE] leading-relaxed">
                  The model is constrained to facts extracted from your resume. Any skill or project not in your profile is flagged and omitted.
                </p>
              </div>

              {/* Feature 2 */}
              <div data-home-feature className="p-6 rounded-2xl border border-[#1E3560] bg-[#101C38] space-y-3 hover:border-[#FF6A3D]/50 transition-colors shadow-lg">
                <div className="h-12 w-12 rounded-xl bg-[#FF6A3D]/15 text-[#FF6A3D] border border-[#FF6A3D]/30 flex items-center justify-center shadow-inner">
                  <Cpu className="h-6 w-6" />
                </div>
                <h3 className="font-semibold text-lg text-[#F1F5F9]">
                  ML Semantic Match Points
                </h3>
                <p className="text-sm text-[#8FA0BE] leading-relaxed">
                  Sentence embeddings rank your projects against job requirements. The top 2 to 3 matches become the concrete proof points in your email.
                </p>
              </div>

              {/* Feature 3 */}
              <div data-home-feature className="p-6 rounded-2xl border border-[#1E3560] bg-[#101C38] space-y-3 hover:border-[#FF6A3D]/50 transition-colors shadow-lg">
                <div className="h-12 w-12 rounded-xl bg-[#FF6A3D]/15 text-[#FF6A3D] border border-[#FF6A3D]/30 flex items-center justify-center shadow-inner">
                  <Clock className="h-6 w-6" />
                </div>
                <h3 className="font-semibold text-lg text-[#F1F5F9]">
                  5-7 Day Follow-Up Scheduler
                </h3>
                <p className="text-sm text-[#8FA0BE] leading-relaxed">
                  Tracks application statuses on a Kanban board and automatically flags follow-ups with one-click follow-up generation.
                </p>
              </div>
            </div>
          </div>

        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#1E3560] py-8 bg-[#0A1128] text-center text-xs text-[#8FA0BE]">
        <p>AI Recruiter Email and Cover Letter Generator • Empowering Students & Freshers</p>
      </footer>
    </div>
    </HomepageMotion>
  );
}


