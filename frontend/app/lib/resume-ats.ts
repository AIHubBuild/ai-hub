import { API_URL, errorMessage } from "./api";

export interface UploadResumeData {
  resume_id: string;
  file_name: string;
  extracted_characters: number;
}

export interface AtsAnalysisData {
  analysis_id: string;
  resume_id: string;
  run_id: string;
  ats_score: number;
  matching_keywords: string[];
  missing_keywords: string[];
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

export async function uploadResume(file: File): Promise<UploadResumeData> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/api/v1/resumes`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  const body = (await response.json()) as Envelope<UploadResumeData>;
  return body.data;
}

export async function runAtsAnalysis(
  resumeId: string,
  jobDescription: string,
): Promise<AtsAnalysisData> {
  const response = await fetch(
    `${API_URL}/api/v1/resumes/${resumeId}/ats-analysis`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: jobDescription }),
    },
  );
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  const body = (await response.json()) as Envelope<AtsAnalysisData>;
  return body.data;
}

export async function downloadTailoredResumeDocx(
  analysisId: string,
): Promise<Blob> {
  const response = await fetch(
    `${API_URL}/api/v1/analyses/${analysisId}/tailored-resume.docx`,
  );
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return response.blob();
}
