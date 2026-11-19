import { WorkspaceShell } from "@/components/WorkspaceShell";
import { JobDiscovery } from "@/components/JobDiscovery";

export default function JobsPage(){return <WorkspaceShell section="Job Discovery"><main className="workspace-main p-4 sm:p-8 space-y-6"><div><h1 className="text-3xl font-bold">Smart job discovery</h1><p className="text-[#BAC7DE]">Search attributed listings, import official URLs, and rank opportunities against verified evidence.</p></div><JobDiscovery/></main></WorkspaceShell>;}
