import { API_URL, ApiError, errorMessage } from "./api";
import { authHeaders } from "./supabase";

export interface UploadResumeData {
  resume_id: string;
  file_name: string;
  extracted_characters: number;
}

export interface RequirementEvidence {
  term: string;
  status: string;
  category: string;
  evidence: string[];
  section?: string | null;
  detail?: string;
  mandatory?: boolean;
}

export interface ScoreBreakdown {
  category: string;
  weight: number;
  total: number;
  supported: number;
  partial: number;
  unverified?: number;
  missing: number;
  score: number;
}

export interface WritingIssue {
  code: string;
  message: string;
}

export interface WritingReview {
  passed: boolean;
  issues: WritingIssue[];
}


export interface DocumentValidationIssue {
  document: string;
  severity: "error" | "warning";
  code: string;
  message: string;
  excerpt?: string;
  source?: string;
}

export interface DocumentValidationDocument {
  blocking_issues: DocumentValidationIssue[];
  warnings: DocumentValidationIssue[];
  pages: number;
}

export interface DocumentValidationReport {
  ready: boolean;
  documents: {
    cv: DocumentValidationDocument;
    cover_letter: DocumentValidationDocument;
  };
  ai_review_available: boolean;
  ai_review_error: string | null;
}

export interface AtsAnalysisData {
  analysis_id: string;
  resume_id: string;
  run_id: string;
  ats_score: number;
  score_label: string;
  requirement_coverage?: number | null;
  evidence_confidence?: number | null;
  matching_keywords: string[];
  partial_keywords: string[];
  unverified_keywords?: string[];
  missing_keywords: string[];
  requirement_analysis: RequirementEvidence[] | null;
  score_breakdown: ScoreBreakdown[] | null;
  job_description_warning: string | null;
  writing_review: WritingReview | null;
  improvement_suggestions: string | null;
  tailored_resume: string | null;
  cover_letter: string | null;
}

interface Envelope<T> {
  success: boolean;
  message: string;
  data: T;
}

export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt"] as const;

async function requireOk<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

export async function uploadResume(file: File): Promise<UploadResumeData> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/api/v1/resumes`, {
    method: "POST",
    body: formData,
    headers: await authHeaders(),
  });
  const body = await requireOk<Envelope<UploadResumeData>>(response);
  return body.data;
}

export async function runAtsAnalysis(
  resumeId: string,
  jobDescription: string,
  styleNotes?: string,
): Promise<AtsAnalysisData> {
  const response = await fetch(
    `${API_URL}/api/v1/resumes/${resumeId}/ats-analysis`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await authHeaders()),
      },
      body: JSON.stringify({
        job_description: jobDescription,
        style_notes: styleNotes?.trim() || null,
      }),
    },
  );
  const body = await requireOk<Envelope<AtsAnalysisData>>(response);
  return body.data;
}

export async function downloadTailoredResumeDocx(
  analysisId: string,
): Promise<Blob> {
  const response = await fetch(
    `${API_URL}/api/v1/analyses/${analysisId}/tailored-resume.docx`,
    { headers: await authHeaders() },
  );
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return response.blob();
}

export async function downloadCoverLetterDocx(
  analysisId: string,
): Promise<Blob> {
  return downloadDocument(
    analysisId,
    "tailored-cover-letter.docx",
  );
}

export async function downloadTailoredResumePdf(
  analysisId: string,
): Promise<Blob> {
  return downloadDocument(analysisId, "tailored-resume.pdf");
}

export async function downloadCoverLetterPdf(
  analysisId: string,
): Promise<Blob> {
  return downloadDocument(analysisId, "tailored-cover-letter.pdf");
}

async function downloadDocument(
  analysisId: string,
  filename: string,
): Promise<Blob> {
  const response = await fetch(
    `${API_URL}/api/v1/analyses/${analysisId}/${filename}`,
    { headers: await authHeaders() },
  );
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return response.blob();
}

export async function fetchDocumentValidation(
  analysisId: string,
): Promise<DocumentValidationReport> {
  const response = await fetch(
    `${API_URL}/api/v1/analyses/${analysisId}/document-validation`,
    { headers: await authHeaders(), cache: "no-store" },
  );
  const body = await requireOk<
    Envelope<DocumentValidationReport>
  >(response);
  return body.data;
}

export function previewTailoredResumePdf(
  analysisId: string,
): Promise<Blob> {
  return downloadDocument(
    analysisId,
    "tailored-resume.pdf?preview=true",
  );
}

export function previewCoverLetterPdf(
  analysisId: string,
): Promise<Blob> {
  return downloadDocument(
    analysisId,
    "tailored-cover-letter.pdf?preview=true",
  );
}
