"use client";

import { useRef, useState } from "react";
import {
  AtsAnalysisData,
  SUPPORTED_EXTENSIONS,
  downloadTailoredResumeDocx,
  runAtsAnalysis,
  uploadResume,
} from "../../lib/resume-ats";

type Stage = "idle" | "uploading" | "analyzing" | "error" | "done";

const ACCEPT = SUPPORTED_EXTENSIONS.join(",");

export function AtsWorkspace() {
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [result, setResult] = useState<AtsAnalysisData | null>(null);
  const [downloading, setDownloading] = useState(false);
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
    setResult(null);
    setStage("uploading");
    try {
      const uploaded = await uploadResume(file);
      setStage("analyzing");
      const analysis = await runAtsAnalysis(
        uploaded.resume_id,
        jobDescription.trim(),
      );
      setResult(analysis);
      setStage("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error.");
      setStage("error");
    }
  }

  async function handleDownload() {
    if (!result) return;
    setDownloading(true);
    try {
      const blob = await downloadTailoredResumeDocx(result.analysis_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "tailored-resume.docx";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Download failed.");
      setStage("error");
    } finally {
      setDownloading(false);
    }
  }

  function reset() {
    setStage("idle");
    setError(null);
    setResult(null);
    setFileName(null);
    setJobDescription("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
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
              Analysis failed
            </h3>
            <p className="mt-1 text-sm leading-relaxed text-red-700 dark:text-red-400">
              {error}
            </p>
            <button
              type="button"
              onClick={reset}
              className="mt-3 inline-flex items-center rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900"
            >
              Try again
            </button>
          </div>
        )}

        {stage === "done" && result !== null && (
          <div>
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
                  ATS analysis complete
                </h2>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                  Score computed by the deterministic keyword engine.
                </p>
              </div>
              <div className="text-right">
                <div className="text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                  {result.ats_score}
                </div>
                <div className="text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  ATS score
                </div>
              </div>
            </div>

            <KeywordSection
              title="Matching keywords"
              keywords={result.matching_keywords}
              tone="matched"
            />
            <KeywordSection
              title="Missing keywords"
              keywords={result.missing_keywords}
              tone="missing"
            />

            {result.improvement_suggestions && (
              <TextSection
                title="Improvement suggestions"
                text={result.improvement_suggestions}
              />
            )}
            {result.tailored_resume && (
              <TextSection title="Tailored resume" text={result.tailored_resume} />
            )}
            {result.cover_letter && (
              <TextSection title="Cover letter" text={result.cover_letter} />
            )}

            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-zinc-100 pt-5 dark:border-zinc-800">
              {result.tailored_resume && (
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={downloading}
                  className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
                >
                  {downloading ? "Preparing DOCX…" : "Download tailored resume (DOCX)"}
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
  tone: "matched" | "missing";
}) {
  if (keywords.length === 0) {
    return null;
  }
  const chip =
    tone === "matched"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400"
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
