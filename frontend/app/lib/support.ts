import { API_URL, ApiError, errorMessage } from "./api";
import { authHeaders } from "./supabase";

export interface TicketData {
  ticket_id: string;
  priority: string;
  assigned_team: string;
  status: string;
}

export interface SupportMessage {
  role: string;
  content: string;
}

interface Envelope<T> {
  success: boolean;
  message: string;
  data: T;
}

export async function createSupportSession(): Promise<string> {
  const response = await fetch(`${API_URL}/api/v1/support/sessions`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const body = (await response.json()) as Envelope<{ session_id: string }>;
  return body.data.session_id;
}

export interface SendMessageResult {
  session_id: string;
  status: string;
  issue_type: string | null;
  ticket: TicketData | null;
  escalation_needed: boolean;
  follow_up_question: string | null;
  response: string;
}

export async function sendSupportMessage(
  sessionId: string,
  message: string,
): Promise<SendMessageResult> {
  const response = await fetch(
    `${API_URL}/api/v1/support/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await authHeaders()),
      },
      body: JSON.stringify({ message }),
    },
  );
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const body = (await response.json()) as Envelope<SendMessageResult>;
  return body.data;
}

export interface SupportSessionDetail {
  session_id: string;
  status: string;
  issue_type: string | null;
  messages: SupportMessage[];
  ticket: TicketData | null;
}

export interface SupportSessionSummary {
  session_id: string;
  status: string;
  issue_type: string | null;
  created_at: string;
}

export async function listSupportSessions(): Promise<SupportSessionSummary[]> {
  const response = await fetch(`${API_URL}/api/v1/support/sessions`, {
    headers: await authHeaders(),
  });
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const body = (await response.json()) as Envelope<{
    sessions: SupportSessionSummary[];
  }>;
  return body.data.sessions;
}

export async function fetchSupportSession(
  sessionId: string,
): Promise<SupportSessionDetail> {
  const response = await fetch(
    `${API_URL}/api/v1/support/sessions/${sessionId}`,
    { headers: await authHeaders() },
  );
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const body = (await response.json()) as Envelope<SupportSessionDetail>;
  return body.data;
}
