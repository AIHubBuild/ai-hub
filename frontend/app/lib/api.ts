const configuredUrl = process.env.NEXT_PUBLIC_API_URL;

if (!configuredUrl && process.env.NODE_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not configured for this build. Set it to the production backend origin (e.g. https://api.aihubassist.com) in the deployment environment and rebuild.",
  );
}

export const API_URL = configuredUrl ?? "http://localhost:8000";

export interface ErrorEnvelope {
  success: false;
  message: string;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as Partial<ErrorEnvelope>;
    if (typeof body.message === "string" && body.message) {
      return body.message;
    }
  } catch {
    // Fall through to the generic message.
  }
  return `Request failed with status ${response.status}.`;
}
