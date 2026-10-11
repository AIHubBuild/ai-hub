import Link from "next/link";
import { ArrowLeftIcon } from "../../components/icons";
import { AtsWorkspace } from "./ats-workspace";

export default function ResumeAtsAppPage() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <Link
        href="/#assistants"
        className="mb-8 inline-flex items-center text-sm text-zinc-500 transition-colors hover:text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
      >
        <ArrowLeftIcon />
        All assistants
      </Link>

      <section aria-labelledby="ats-heading" className="mb-10 max-w-2xl">
        <h1
          id="ats-heading"
          className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
        >
          ATS Resume Assistant
        </h1>
        <p className="mt-3 text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          Upload your resume (PDF, DOCX, or TXT), paste the target job
          description, and get an ATS score, keyword findings, actionable
          suggestions, a tailored resume, and a cover letter — with a
          downloadable DOCX.
        </p>
      </section>

      <AtsWorkspace />
    </main>
  );
}
