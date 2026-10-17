"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useAuth } from "../../components/auth/auth-provider";
import { ApiError } from "../../lib/api";
import { DocumentTextIcon } from "../../components/icons";
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
type ResultTab = "suggestions" | "resume" | "cover";

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
  const [resultTab, setResultTab] = useState<ResultTab>("suggestions");
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
    setResultTab("suggestions");
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
    setResultTab("suggestions");
    setFileName(null);
    setJobDescription("");
    setStyleNotes("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  const coverLetterText = (result?.cover_letter ?? "").trim();
  const hasCoverLetter = coverLetterText.length > 0;

  const scoreTone =
    (result?.ats_score ?? 0) >= 75
      ? "text-success"
      : (result?.ats_score ?? 0) >= 50
        ? "text-ink"
        : "text-danger";

  if (authLoading) {
    return (
      <div className="flex min-h-48 items-center justify-center rounded-[28px] bg-surface ring-1 ring-line/80">
        <div
          aria-hidden="true"
          className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-accent"
        />
      </div>
    );
  }

  if (session === null) {
    return (
      <div className="rounded-[28px] bg-surface p-8 text-center ring-1 ring-line/80 sm:p-10">
        <h2 className="ui-display text-2xl text-ink">
          Sign in to use the ATS Resume Assistant
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          Your resume analyses and generated documents are private to your
          account. Sign in to upload a resume and run an ATS analysis.
        </p>
        <Link
          href="/login?redirect=/apps/resume-ats"
          className="ui-button ui-button-primary mt-5"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[28px] bg-surface ring-1 ring-line/80">
      <div className="grid lg:grid-cols-[390px_minmax(0,1fr)]">
      <form
        onSubmit={handleSubmit}
        className="border-b border-line bg-surface-muted/55 p-6 sm:p-8 lg:border-b-0 lg:border-r"
      >
        <div className="mb-7">
          <p className="ui-eyebrow">New analysis</p>
          <h2 className="ui-display mt-2 text-2xl text-ink">
            Build a job-specific resume
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Add your resume and the role. You will see the evidence behind
            the score before you download anything.
          </p>
        </div>

        <label
          htmlFor="resume-file"
          className="mb-2 flex items-center gap-3 text-sm font-semibold text-ink"
        >
          <span aria-hidden="true" className="font-mono text-[11px] text-muted">
            01
          </span>
          Resume file
        </label>
        <div className="flex items-center gap-3 rounded-xl border border-dashed border-line bg-surface px-3.5 py-3.5 transition-colors focus-within:border-accent">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
            <DocumentTextIcon className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <input
              id="resume-file"
              ref={fileInputRef}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              onChange={(event) =>
                setFileName(event.target.files?.[0]?.name ?? null)
              }
            />
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <label
                htmlFor="resume-file"
                className="ui-button ui-button-secondary cursor-pointer px-3 py-1.5 text-xs"
              >
                {fileName ? "Replace file" : "Choose file"}
              </label>
              <p className="min-w-0 truncate text-xs text-muted">
                {fileName ?? "PDF, DOCX, or TXT. Up to 5 MB."}
              </p>
            </div>
          </div>
        </div>

        <label
          htmlFor="job-description"
          className="mb-2 mt-6 flex items-center gap-3 text-sm font-semibold text-ink"
        >
          <span aria-hidden="true" className="font-mono text-[11px] text-muted">
            02
          </span>
          Job description
        </label>
        <textarea
          id="job-description"
          value={jobDescription}
          onChange={(event) => setJobDescription(event.target.value)}
          rows={8}
          placeholder="Paste the target job description here…"
          className="ui-field resize-none"
        />

        <label
          htmlFor="style-notes"
          className="mb-2 mt-6 flex items-center gap-3 text-sm font-semibold text-ink"
        >
          <span aria-hidden="true" className="font-mono text-[11px] text-muted">
            03
          </span>
          Style preferences <span className="font-normal text-muted">(optional)</span>
        </label>
        <textarea
          id="style-notes"
          value={styleNotes}
          onChange={(event) => setStyleNotes(event.target.value)}
          rows={2}
          maxLength={500}
          placeholder="e.g. Keep it factual, short sentences, UK spelling…"
          className="ui-field resize-none"
        />

        <button
          type="submit"
          disabled={!canSubmit}
          className="ui-button ui-button-primary mt-6 w-full"
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
        className="min-h-[32rem] p-6 sm:p-8"
      >
        {stage === "idle" && (
          <div className="flex h-full min-h-[26rem] flex-col justify-between">
            <div>
              <p className="ui-eyebrow">Results</p>
              <h2 className="ui-display mt-3 text-3xl text-ink">
                A clear read on the fit.
              </h2>
              <p className="mt-3 max-w-md text-sm leading-6 text-muted">
                You will see the estimated match, the evidence behind it,
                and the gaps worth addressing before you download anything.
              </p>
            </div>
            <dl className="grid gap-5 border-t border-line pt-6 sm:grid-cols-3">
              <div>
                <dt className="text-sm font-semibold text-ink">Match score</dt>
                <dd className="mt-1 text-xs leading-5 text-muted">
                  Weighted coverage of the requirements found in the job
                  description.
                </dd>
              </div>
              <div>
                <dt className="text-sm font-semibold text-ink">
                  Keyword evidence
                </dt>
                <dd className="mt-1 text-xs leading-5 text-muted">
                  Found, partial, and missing terms, each tied to your
                  resume.
                </dd>
              </div>
              <div>
                <dt className="text-sm font-semibold text-ink">
                  Ready to export
                </dt>
                <dd className="mt-1 text-xs leading-5 text-muted">
                  Review the suggestions, tailored resume, and cover letter
                  first.
                </dd>
              </div>
            </dl>
          </div>
        )}

        {(stage === "uploading" || stage === "analyzing") && (
          <div className="flex h-full min-h-[26rem] flex-col items-center justify-center text-center">
            <div
              aria-hidden="true"
              className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-accent"
            />
            <p className="mt-5 text-sm font-semibold text-ink">
              {stage === "uploading"
                ? "Uploading and extracting your resume"
                : "Building your analysis"}
            </p>
            <p className="mt-1 max-w-xs text-xs leading-5 text-muted">
              {stage === "uploading"
                ? "This usually takes a few seconds."
                : "Generating the score, suggestions, resume, and cover letter can take up to a minute."}
            </p>
          </div>
        )}

        {stage === "error" && (
          <div className="rounded-2xl bg-surface-muted p-5 ring-1 ring-line">
            <p className="ui-eyebrow text-danger">
              {errorIsAuth ? "Session expired" : "Analysis failed"}
            </p>
            <h3 className="ui-display mt-3 text-2xl text-ink">
              {errorIsAuth
                ? "Sign in again to continue."
                : "That analysis did not finish."}
            </h3>
            <p className="mt-2 text-sm leading-6 text-ink-soft">{error}</p>
            {errorIsAuth ? (
              <Link
                href="/login?redirect=/apps/resume-ats"
                className="ui-button ui-button-primary mt-5"
              >
                Sign in again
              </Link>
            ) : (
              <button
                type="button"
                onClick={reset}
                className="ui-button ui-button-secondary mt-5"
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
                className="mb-6 border-l-2 border-amber-500 bg-surface-muted px-4 py-3 text-sm leading-6 text-ink-soft"
              >
                {result.job_description_warning}
              </div>
            )}

            <div className="border-b border-line pb-6">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="ui-eyebrow">Estimated match</p>
                  <h2 className="ui-display mt-2 text-3xl text-ink">
                    {result.score_label}
                  </h2>
                  <p className="mt-2 max-w-md text-sm leading-6 text-muted">
                    {result.requirement_coverage != null && (
                      <>
                        Requirement coverage{" "}
                        <strong className="font-semibold text-ink">
                          {result.requirement_coverage}%
                        </strong>
                        {" · "}Evidence confidence{" "}
                        <strong className="font-semibold text-ink">
                          {result.evidence_confidence ?? 0}%
                        </strong>
                        .{" "}
                      </>
                    )}
                    This is an estimate from your resume and this job
                    description, not an employer&apos;s ATS score.
                  </p>
                </div>
                <div className="flex items-end gap-2">
                  <span
                    className={`ui-display text-7xl leading-none ${scoreTone}`}
                  >
                    {result.ats_score}
                  </span>
                  <span className="mb-2 text-xs font-medium text-muted">
                    / 100
                  </span>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
                <span>
                  <strong className="font-semibold text-ink">
                    {result.matching_keywords.length}
                  </strong>{" "}
                  matched keywords
                </span>
                <span>
                  <strong className="font-semibold text-ink">
                    {result.partial_keywords.length}
                  </strong>{" "}
                  partial keywords
                </span>
                <span>
                  <strong className="font-semibold text-ink">
                    {result.unverified_keywords?.length ?? 0}
                  </strong>{" "}
                  unverified keywords
                </span>
                <span>
                  <strong className="font-semibold text-ink">
                    {result.missing_keywords.length}
                  </strong>{" "}
                  missing keywords
                </span>
              </div>
            </div>

            {result.ats_score === 0 && (
              <p className="mt-5 border-l-2 border-amber-500 bg-surface-muted px-4 py-3 text-sm leading-6 text-ink-soft">
                None of the requirements detected in this job description
                were found in your resume, so the estimated score is 0.
                Review the requirement evidence below to see exactly what
                was checked.
              </p>
            )}

            {result.score_breakdown !== null &&
              result.score_breakdown.length > 0 && (
                <details className="group border-b border-line">
                  <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-semibold text-ink marker:content-none">
                    Score breakdown
                    <span
                      aria-hidden="true"
                      className="text-muted transition-transform group-open:rotate-180"
                    >
                      ▾
                    </span>
                  </summary>
                  <ul>
                    {result.score_breakdown.map((entry) => (
                      <li
                        key={entry.category}
                        className="flex flex-wrap items-baseline justify-between gap-2 py-2.5 text-sm"
                      >
                        <span className="font-medium text-ink">
                          {CATEGORY_LABELS[entry.category] ?? entry.category}
                        </span>
                        <span className="text-xs text-muted">
                          {entry.score}% · {entry.supported}/{entry.total} matched
                          {" · "}
                          {entry.partial} partial · {entry.unverified ?? 0}{" "}
                          unverified · {entry.missing} missing
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}

            <details className="group border-b border-line">
              <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-semibold text-ink marker:content-none">
                How is this score calculated?
                <span
                  aria-hidden="true"
                  className="text-muted transition-transform group-open:rotate-180"
                >
                  ▾
                </span>
              </summary>
              <p className="pb-4 text-sm leading-6 text-muted">
                Every meaningful requirement in the job description is
                grouped into skills, experience, responsibilities,
                qualifications, achievements, or communication, then
                checked against the resume. Requirements are marked
                matched, partial, unverified (the term appears without
                enough context), or missing. The estimate combines
                weighted requirement coverage with evidence confidence
                across those dimensions. It is an estimate, not a
                reproduction of any employer&apos;s ATS.
              </p>
            </details>

            <div className="mt-6 grid gap-0 border-b border-line pb-6 sm:grid-cols-2 sm:divide-x sm:divide-line lg:grid-cols-4">
              <KeywordColumn
                title="Matched"
                keywords={result.matching_keywords}
                tone="matched"
              />
              <KeywordColumn
                title="Partial"
                keywords={result.partial_keywords}
                tone="partial"
              />
              <KeywordColumn
                title="Unverified"
                keywords={result.unverified_keywords ?? []}
                tone="unverified"
              />
              <KeywordColumn
                title="Missing"
                keywords={result.missing_keywords}
                tone="missing"
              />
            </div>

            <EvidenceSection requirements={result.requirement_analysis} />

            {result.writing_review !== null &&
              result.writing_review.issues.length > 0 && (
                <details className="group border-b border-line">
                  <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-semibold text-ink marker:content-none">
                    Writing quality notes ({result.writing_review.issues.length})
                    <span
                      aria-hidden="true"
                      className="text-muted transition-transform group-open:rotate-180"
                    >
                      ▾
                    </span>
                  </summary>
                  <ul className="list-disc space-y-1 pb-4 pl-5 text-sm leading-6 text-muted">
                    {result.writing_review.issues.map((issue) => (
                      <li key={issue.code + issue.message}>{issue.message}</li>
                    ))}
                  </ul>
                </details>
              )}

            {(result.improvement_suggestions ||
              result.tailored_resume ||
              hasCoverLetter) && (
              <AiOutputPanel
                result={result}
                activeTab={
                  resultTab === "suggestions" && result.improvement_suggestions
                    ? "suggestions"
                    : resultTab === "resume" && result.tailored_resume
                      ? "resume"
                      : resultTab === "cover" && hasCoverLetter
                        ? "cover"
                        : result.improvement_suggestions
                          ? "suggestions"
                          : result.tailored_resume
                            ? "resume"
                            : "cover"
                }
                onTabChange={setResultTab}
                downloading={downloading}
                downloadingCoverLetter={downloadingCoverLetter}
                onDownload={handleDownload}
                onDownloadCoverLetter={handleDownloadCoverLetter}
              />
            )}

            {downloadError !== null && (
              <div
                role="alert"
                className="mt-5 border-l-2 border-danger bg-surface-muted px-4 py-3 text-sm leading-6 text-ink-soft"
              >
                {downloadError}
              </div>
            )}

            <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
              <p className="font-mono text-[11px] text-muted">
                Analysis {result.analysis_id.slice(0, 8)}
              </p>
              <button
                type="button"
                onClick={reset}
                className="ui-button ui-button-secondary"
              >
                New analysis
              </button>
            </div>
          </div>
        )}
      </section>
      </div>
    </div>
  );
}

function KeywordColumn({
  title,
  keywords,
  tone,
}: {
  title: string;
  keywords: string[];
  tone: "matched" | "missing" | "partial" | "unverified";
}) {
  const chip =
    tone === "matched"
      ? "bg-success/10 text-success"
      : tone === "partial"
        ? "bg-accent-soft text-accent"
        : tone === "unverified"
          ? "bg-surface-muted text-ink"
          : "bg-surface-muted text-muted";
  return (
    <section className="py-4 first:pt-0 last:pb-0 sm:px-5 sm:py-0 sm:first:pl-0 sm:last:pr-0">
      <h3 className="mb-3 flex items-center justify-between text-sm font-semibold text-ink">
        {title}
        <span className="font-mono text-[11px] font-normal text-muted">
          {keywords.length}
        </span>
      </h3>
      {keywords.length === 0 ? (
        <p className="text-xs text-muted">None detected</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {keywords.map((keyword) => (
            <li key={keyword} className={`rounded-md px-2 py-1 text-xs ${chip}`}>
              {keyword}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const STATUS_LABELS: Record<string, string> = {
  matched: "Matched",
  supported: "Matched",
  partial: "Partial",
  unverified: "Unverified",
  missing: "Missing",
};

const CATEGORY_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  responsibilities: "Responsibilities",
  qualifications: "Qualifications",
  achievements: "Achievements",
  communication: "Communication",
  essential: "Essential",
  preferred: "Preferred",
  technical_skills: "Technical skill",
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
    <details className="group border-b border-line">
      <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-semibold text-ink marker:content-none">
        Requirement evidence
        <span
          aria-hidden="true"
          className="text-muted transition-transform group-open:rotate-180"
        >
          ▾
        </span>
      </summary>
      <div className="space-y-4 pb-5">
        {requirements.map((requirement) => (
          <div key={requirement.term}>
            <p className="text-sm">
              <span className="font-semibold text-ink">
                {requirement.term}
              </span>{" "}
              <span className="text-xs uppercase tracking-wide text-muted">
                {CATEGORY_LABELS[requirement.category] ?? requirement.category} ·{" "}
                {STATUS_LABELS[requirement.status] ?? requirement.status}
                {requirement.mandatory === false ? " · Preferred" : ""}
              </span>
            </p>
            {requirement.detail ? (
              <p className="mt-1 text-xs leading-5 text-muted">
                {requirement.detail}
              </p>
            ) : null}
            {requirement.evidence.length > 0 ? (
              <ul className="mt-1.5 space-y-0.5 border-l border-line pl-3 text-xs leading-5 text-muted">
                {requirement.evidence.map((line) => (
                  <li key={line}>“{line}”</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1.5 text-xs text-muted">
                No evidence in the resume.
              </p>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

function AiOutputPanel({
  result,
  activeTab,
  onTabChange,
  downloading,
  downloadingCoverLetter,
  onDownload,
  onDownloadCoverLetter,
}: {
  result: AtsAnalysisData;
  activeTab: ResultTab;
  onTabChange: (tab: ResultTab) => void;
  downloading: boolean;
  downloadingCoverLetter: boolean;
  onDownload: () => void;
  onDownloadCoverLetter: () => void;
}) {
  const tabs: { id: ResultTab; label: string; visible: boolean }[] = [
    {
      id: "suggestions",
      label: "Suggestions",
      visible: Boolean(result.improvement_suggestions),
    },
    {
      id: "resume",
      label: "Tailored resume",
      visible: Boolean(result.tailored_resume),
    },
    {
      id: "cover",
      label: "Cover letter",
      visible: Boolean((result.cover_letter ?? "").trim()),
    },
  ];
  const visible = tabs.filter((tab) => tab.visible);

  return (
    <section aria-labelledby="ai-output-heading" className="mt-7">
      <h3 id="ai-output-heading" className="ui-eyebrow">
        Generated documents
      </h3>
      <div
        role="tablist"
        aria-label="Generated documents"
        className="mt-3 flex flex-wrap gap-6 border-b border-line"
      >
        {visible.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`-mb-px border-b-2 pb-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              activeTab === tab.id
                ? "border-accent text-ink"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-5">
        {activeTab === "suggestions" && result.improvement_suggestions && (
          <div className="whitespace-pre-wrap text-sm leading-7 text-ink-soft">
            {result.improvement_suggestions}
          </div>
        )}
        {activeTab === "resume" && result.tailored_resume && (
          <>
            <div className="whitespace-pre-wrap text-sm leading-7 text-ink-soft">
              {result.tailored_resume}
            </div>
            <div className="mt-5 flex justify-end border-t border-line pt-4">
              <button
                type="button"
                onClick={onDownload}
                disabled={downloading}
                aria-label="Download tailored resume as a DOCX file"
                className="ui-button ui-button-primary"
              >
                {downloading ? "Preparing DOCX…" : "Download DOCX"}
              </button>
            </div>
          </>
        )}
        {activeTab === "cover" && (result.cover_letter ?? "").trim() && (
          <>
            <div className="whitespace-pre-wrap text-sm leading-7 text-ink-soft">
              {result.cover_letter}
            </div>
            <div className="mt-5 flex justify-end border-t border-line pt-4">
              <button
                type="button"
                onClick={onDownloadCoverLetter}
                disabled={downloadingCoverLetter}
                aria-label="Download cover letter as a DOCX file"
                className="ui-button ui-button-secondary"
              >
                {downloadingCoverLetter ? "Preparing DOCX…" : "Download DOCX"}
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
