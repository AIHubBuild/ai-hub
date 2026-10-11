"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useAuth } from "../../components/auth/auth-provider";
import { ApiError } from "../../lib/api";
import {
  AtsAnalysisData,
  RequirementEvidence,
  SUPPORTED_EXTENSIONS,
  downloadCoverLetterDocx,
  downloadTailoredResumeDocx,
  runAtsAnalysis,
  uploadResume,
} from "../../lib/resume-ats";

type Stage = "idle" | "uploading" | "analyzing" | "error" | "done";

const ACCEPT = SUPPORTED_EXTENSIONS.join(",");

export function AtsWorkspace() {
  const { session, loading: authLoading } = useAuth();
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [errorIsAuth, setErrorIsAuth] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [styleNotes, setStyleNotes] = useState("");
  const [result, setResult] = useState<AtsAnalysisData | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadingCoverLetter, setDownloadingCoverLetter] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSubmit =
    stage !== "uploading" &&
    stage !== "analyzing" &&
    fileName !== null &&
    jobDescription.trim().length > 0;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file || !jobDescription.trim()) {
      return;
    }

    setError(null);
    setErrorIsAuth(false);
    setResult(null);
    setStage("uploading");
    try {
      const uploaded = await uploadResume(file);
      setStage("analyzing");
      const analysis = await runAtsAnalysis(
        uploaded.resume_id,
        jobDescription.trim(),
        styleNotes,
      );
      setResult(analysis);
      setStage("done");
    } catch (caught) {
      const isAuth =
        caught instanceof ApiError && (caught.status === 401 || caught.status === 403);
      setErrorIsAuth(isAuth);
      setError(caught instanceof Error ? caught.message : "Unexpected error.");
      setStage("error");
    }
  }

  async function triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function handleDownload() {
    if (!result) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const blob = await downloadTailoredResumeDocx(result.analysis_id);
      triggerDownload(blob, "tailored-resume.docx");
    } catch (caught) {
      setDownloadError(
        caught instanceof Error ? caught.message : "Download failed.",
      );
    } finally {
      setDownloading(false);
    }
  }

  async function handleDownloadCoverLetter() {
    if (!result) return;
    setDownloadingCoverLetter(true);
    setDownloadError(null);
    try {
      const blob = await downloadCoverLetterDocx(result.analysis_id);
      triggerDownload(blob, "tailored-cover-letter.docx");
    } catch (caught) {
      setDownloadError(
        caught instanceof Error
          ? caught.message
          : "Cover letter download failed.",
      );
    } finally {
      setDownloadingCoverLetter(false);
    }
  }

  function reset() {
    setStage("idle");
    setError(null);
    setErrorIsAuth(false);
    setDownloadError(null);
    setResult(null);
    setFileName(null);
    setJobDescription("");
    setStyleNotes("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  const coverLetterText = (result?.cover_letter ?? "").trim();
  const hasCoverLetter = coverLetterText.length > 0;

  if (authLoading) {
    return (
      <div className="flex min-h-48 items-center justify-center rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div
          aria-hidden="true"
          className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-zinc-50"
        />
      </div>
    );
  }

  if (session === null) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
          Sign in to use the ATS Resume Assistant
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Your resume analyses and generated documents are private to your
          account. Sign in to upload a resume and run an ATS analysis.
        </p>
        <Link
          href="/login?redirect=/apps/resume-ats"
          className="mt-5 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h2 className="mb-4 text-lg font-medium text-zinc-900 dark:text-zinc-50">
          1. Resume &amp; job description
        </h2>

        <label
          htmlFor="resume-file"
          className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          Resume file
        </label>
        <input
          id="resume-file"
          ref={fileInputRef}
          type="file"
          accept={ACCEPT}
          className="block w-full cursor-pointer rounded-lg border border-zinc-200 bg-zinc-50 p-2 text-sm text-zinc-600 file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-zinc-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-zinc-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400 dark:file:bg-zinc-50 dark:file:text-zinc-900 dark:hover:file:bg-zinc-200"
          onChange={(event) =>
            setFileName(event.target.files?.[0]?.name ?? null)
          }
        />
        <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">
          PDF, DOCX, or TXT — up to 5 MB.
        </p>

        <label
          htmlFor="job-description"
          className="mb-1.5 mt-5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          Job description
        </label>
        <textarea
          id="job-description"
          value={jobDescription}
          onChange={(event) => setJobDescription(event.target.value)}
          rows={8}
          placeholder="Paste the target job description here…"
          className="w-full rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-2 focus:outline-offset-2 focus:outline-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-500"
        />

        <label
          htmlFor="style-notes"
          className="mb-1.5 mt-5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
        >
          Style preferences (optional)
        </label>
        <textarea
          id="style-notes"
          value={styleNotes}
          onChange={(event) => setStyleNotes(event.target.value)}
          rows={2}
          maxLength={500}
          placeholder="e.g. Keep it factual, short sentences, UK spelling…"
          className="w-full rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-2 focus:outline-offset-2 focus:outline-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-500"
        />

        <button
          type="submit"
          disabled={!canSubmit}
          className="mt-5 inline-flex w-full items-center justify-center rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
        >
          {stage === "uploading"
            ? "Uploading resume…"
            : stage === "analyzing"
              ? "Running ATS analysis…"
              : "Analyze resume"}
        </button>
      </form>

      <section
        aria-live="polite"
        className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        {stage === "idle" && (
          <div className="flex h-full min-h-48 flex-col items-center justify-center text-center">
            <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
              ATS analysis
            </h2>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
              The deterministic keyword engine computes the score and
              keyword findings; the AI provider adds improvement
              suggestions, a tailored resume, and a cover letter.
            </p>
          </div>
        )}

        {(stage === "uploading" || stage === "analyzing") && (
          <div className="flex h-full min-h-48 flex-col items-center justify-center text-center">
            <div
              aria-hidden="true"
              className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-zinc-50"
            />
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {stage === "uploading"
                ? "Uploading and extracting resume text…"
                : "The AI provider is generating the analysis. This can take up to a minute."}
            </p>
          </div>
        )}

        {stage === "error" && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-300">
              {errorIsAuth ? "Session expired" : "Analysis failed"}
            </h3>
            <p className="mt-1 text-sm leading-relaxed text-red-700 dark:text-red-400">
              {error}
            </p>
            {errorIsAuth ? (
              <Link
                href="/login?redirect=/apps/resume-ats"
                className="mt-3 inline-flex items-center rounded-lg bg-red-700 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500 dark:bg-red-300 dark:text-red-950 dark:hover:bg-red-200"
              >
                Sign in again
              </Link>
            ) : (
              <button
                type="button"
                onClick={reset}
                className="mt-3 inline-flex items-center rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900"
              >
                Try again
              </button>
            )}
          </div>
        )}

        {stage === "done" && result !== null && (
          <div>
            {result.job_description_warning !== null && (
              <div
                role="alert"
                className="mb-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-400"
              >
                {result.job_description_warning}
              </div>
            )}

            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
                  ATS analysis complete
                </h2>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                  Score computed by the deterministic matching engine.
                </p>
              </div>
              <div className="text-right">
                <div className="text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                  {result.ats_score}
                </div>
                <div className="text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {result.score_label}
                </div>
              </div>
            </div>

            <KeywordSection
              title="Matching keywords"
              keywords={result.matching_keywords}
              tone="matched"
            />
            <KeywordSection
              title="Transferable / partial matches"
              keywords={result.partial_keywords}
              tone="partial"
            />
            <KeywordSection
              title="Missing keywords"
              keywords={result.missing_keywords}
              tone="missing"
            />

            <EvidenceSection requirements={result.requirement_analysis} />

            {result.writing_review !== null &&
              result.writing_review.issues.length > 0 && (
                <details className="group mb-3 rounded-lg border border-amber-200 dark:border-amber-900">
                  <summary className="flex cursor-pointer items-center justify-between rounded-lg px-4 py-3 text-sm font-medium text-amber-900 marker:content-none hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-amber-950">
                    Writing quality notes ({result.writing_review.issues.length})
                    <span
                      aria-hidden="true"
                      className="text-amber-600 transition-transform group-open:rotate-180 dark:text-amber-400"
                    >
                      ▾
                    </span>
                  </summary>
                  <ul className="list-disc space-y-1 border-t border-amber-100 px-4 py-3 pl-9 text-sm leading-relaxed text-amber-800 dark:border-amber-900 dark:text-amber-400">
                    {result.writing_review.issues.map((issue) => (
                      <li key={issue.code + issue.message}>{issue.message}</li>
                    ))}
                  </ul>
                </details>
              )}

            {result.improvement_suggestions && (
              <TextSection
                title="Improvement suggestions"
                text={result.improvement_suggestions}
              />
            )}
            {result.tailored_resume && (
              <TextSection title="Tailored resume" text={result.tailored_resume} />
            )}
            {hasCoverLetter && (
              <TextSection title="Cover letter" text={coverLetterText} />
            )}

            {downloadError !== null && (
              <div
                role="alert"
                className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm leading-relaxed text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-400"
              >
                {downloadError}
              </div>
            )}

            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-zinc-100 pt-5 dark:border-zinc-800">
              {result.tailored_resume && (
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={downloading}
                  aria-label="Download tailored resume as a DOCX file"
                  className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
                >
                  {downloading ? "Preparing DOCX…" : "Download tailored resume (DOCX)"}
                </button>
              )}
              {hasCoverLetter && (
                <button
                  type="button"
                  onClick={handleDownloadCoverLetter}
                  disabled={downloadingCoverLetter}
                  aria-label="Download cover letter as a DOCX file"
                  className="inline-flex items-center justify-center rounded-lg border border-zinc-900 px-4 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:border-zinc-50 dark:text-zinc-50 dark:hover:bg-zinc-800 dark:focus-visible:outline-zinc-50"
                >
                  {downloadingCoverLetter
                    ? "Preparing DOCX…"
                    : "Download cover letter (DOCX)"}
                </button>
              )}
              <button
                type="button"
                onClick={reset}
                className="inline-flex items-center rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                New analysis
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function KeywordSection({
  title,
  keywords,
  tone,
}: {
  title: string;
  keywords: string[];
  tone: "matched" | "missing" | "partial";
}) {
  if (keywords.length === 0) {
    return null;
  }
  const chip =
    tone === "matched"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400"
      : tone === "partial"
        ? "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-400"
        : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400";
  return (
    <section className="mb-5">
      <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {title}
      </h3>
      <ul className="flex flex-wrap gap-1.5">
        {keywords.map((keyword) => (
          <li
            key={keyword}
            className={`rounded-md px-2 py-1 text-xs ${chip}`}
          >
            {keyword}
          </li>
        ))}
      </ul>
    </section>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  essential: "Essential",
  preferred: "Preferred",
  technical_skills: "Technical skill",
  responsibilities: "Responsibility",
  experience: "Experience",
  communication: "Communication",
};

function EvidenceSection({
  requirements,
}: {
  requirements: RequirementEvidence[] | null;
}) {
  if (requirements === null || requirements.length === 0) {
    return null;
  }
  return (
    <details className="group mb-3 rounded-lg border border-zinc-200 dark:border-zinc-800">
      <summary className="flex cursor-pointer items-center justify-between rounded-lg px-4 py-3 text-sm font-medium text-zinc-900 marker:content-none hover:bg-zinc-50 dark:text-zinc-50 dark:hover:bg-zinc-900">
        Requirement evidence
        <span
          aria-hidden="true"
          className="text-zinc-400 transition-transform group-open:rotate-180"
        >
          ▾
        </span>
      </summary>
      <div className="space-y-2 border-t border-zinc-100 px-4 py-3 dark:border-zinc-800">
        {requirements.map((requirement) => (
          <div key={requirement.term}>
            <p className="text-sm">
              <span className="font-medium text-zinc-900 dark:text-zinc-50">
                {requirement.term}
              </span>{" "}
              <span className="text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {CATEGORY_LABELS[requirement.category] ?? requirement.category} ·{" "}
                {requirement.status}
              </span>
            </p>
            {requirement.evidence.length > 0 ? (
              <ul className="ml-4 mt-1 list-disc space-y-0.5 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                {requirement.evidence.map((line) => (
                  <li key={line}>“{line}”</li>
                ))}
              </ul>
            ) : (
              <p className="ml-4 mt-1 text-xs text-zinc-500 dark:text-zinc-500">
                No evidence in the resume.
              </p>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

function TextSection({ title, text }: { title: string; text: string }) {
  return (
    <details className="group mb-3 rounded-lg border border-zinc-200 dark:border-zinc-800">
      <summary className="flex cursor-pointer items-center justify-between rounded-lg px-4 py-3 text-sm font-medium text-zinc-900 marker:content-none hover:bg-zinc-50 dark:text-zinc-50 dark:hover:bg-zinc-900">
        {title}
        <span
          aria-hidden="true"
          className="text-zinc-400 transition-transform group-open:rotate-180"
        >
          ▾
        </span>
      </summary>
      <div className="whitespace-pre-wrap border-t border-zinc-100 px-4 py-3 text-sm leading-relaxed text-zinc-700 dark:border-zinc-800 dark:text-zinc-300">
        {text}
      </div>
    </details>
  );
}
