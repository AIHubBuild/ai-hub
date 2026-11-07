import { API_URL, ApiError, errorMessage } from "./api";
import { authHeaders } from "./supabase";

export interface SubscriptionSummary {
  status: string;
  price_id: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  cancel_at: string | null;
  trial_start: string | null;
  trial_end: string | null;
}

export interface BillingStatusData {
  tier: "free" | "pro";
  is_pro: boolean;
  trial_eligible: boolean;
  has_billing_account: boolean;
  price_cents: number;
  price_currency: string;
  trial_hours: number;
  subscription: SubscriptionSummary | null;
}

interface Envelope<T> {
  success: boolean;
  message: string;
  data: T;
}

async function request<T>(
  path: string,
  method: "GET" | "POST",
): Promise<T> {
  const headers = await authHeaders();
  const response = await fetch(`${API_URL}/api/v1/billing${path}`, {
    method,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const body = (await response.json()) as Envelope<T>;
  if (!body.success) {
    throw new ApiError(body.message, response.status);
  }
  return body.data;
}

export function fetchBillingStatus(): Promise<BillingStatusData> {
  return request<BillingStatusData>("/status", "GET");
}

export interface CheckoutSession {
  url: string;
  session_id: string;
  trial_applied: boolean;
}

export function createCheckoutSession(): Promise<CheckoutSession> {
  return request<CheckoutSession>("/checkout", "POST");
}

export function createPortalSession(): Promise<{ url: string }> {
  return request<{ url: string }>("/portal", "POST");
}
