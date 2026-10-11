export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
