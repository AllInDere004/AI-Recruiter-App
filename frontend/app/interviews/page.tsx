import { WorkspaceShell } from "@/components/WorkspaceShell";
import { InterviewPractice } from "@/components/InterviewPractice";

export default function InterviewsPage(){return <WorkspaceShell section="Interview Practice"><main className="workspace-main space-y-6 p-4 sm:p-8"><div><h1 className="text-3xl font-bold">Interview practice</h1><p className="text-[#BAC7DE]">Practice job-aware questions and receive evidence-based AI feedback.</p></div><InterviewPractice/></main></WorkspaceShell>}
