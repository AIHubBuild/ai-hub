import { AppHeader } from "../../components/app-header";
import { DocumentTextIcon } from "../../components/icons";
import { AtsWorkspace } from "./ats-workspace";

export default function ResumeAtsAppPage() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
      <AppHeader
        eyebrow="Resume ATS"
        title="ATS Resume Assistant"
        description="Upload your resume, paste the target job description, and get a transparent match score, keyword findings, actionable suggestions, a tailored resume, and a cover letter."
        icon={<DocumentTextIcon className="h-4 w-4" />}
      />
      <AtsWorkspace />
    </main>
  );
}
