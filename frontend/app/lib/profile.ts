import { Session } from "@supabase/supabase-js";
import { API_URL, ApiError, errorMessage } from "./api";
import { authHeaders } from "./supabase";

export const PROFILE_POLICY_VERSION = "2026-10-19";

export interface UserProfileData {
  user_id: string;
  full_name: string;
  phone: string | null;
  country_code: string | null;
  city: string | null;
  career_goal: string | null;
  marketing_consent: boolean;
  terms_accepted_at: string;
  terms_version: string;
  privacy_accepted_at: string;
  privacy_version: string;
  created_at: string;
  updated_at: string;
  email: string | null;
  email_verified: boolean;
}

export interface ProfileUpsertPayload {
  full_name: string;
  phone: string | null;
  country_code: string | null;
  city: string | null;
  career_goal: string | null;
  marketing_consent: boolean;
  terms_accepted: boolean;
  privacy_accepted: boolean;
}

interface ProfileEnvelope {
  success: boolean;
  message: string;
  data: UserProfileData;
}

async function requestProfile(
  method: "GET" | "PUT",
  body?: ProfileUpsertPayload,
): Promise<UserProfileData | null> {
  const headers = await authHeaders();
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${API_URL}/api/v1/profile`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const payload = (await response.json()) as ProfileEnvelope;
  if (!payload.success) {
    throw new ApiError(payload.message, response.status);
  }
  return payload.data;
}

export function fetchProfile(): Promise<UserProfileData | null> {
  return requestProfile("GET");
}

export function saveProfile(
  payload: ProfileUpsertPayload,
): Promise<UserProfileData | null> {
  return requestProfile("PUT", payload);
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function profilePayloadFromSession(
  session: Session,
): ProfileUpsertPayload | null {
  const metadata = session.user.user_metadata ?? {};
  const fullName = optionalString(metadata.full_name);
  if (!fullName) {
    return null;
  }
  return {
    full_name: fullName,
    phone: optionalString(metadata.phone),
    country_code: optionalString(metadata.country_code)?.toUpperCase() ?? null,
    city: optionalString(metadata.city),
    career_goal: optionalString(metadata.career_goal),
    marketing_consent: metadata.marketing_consent === true,
    terms_accepted: metadata.terms_accepted === true,
    privacy_accepted: metadata.privacy_accepted === true,
  };
}

export async function ensureProfileFromSession(
  session: Session,
): Promise<boolean> {
  const existing = await fetchProfile();
  if (existing !== null) {
    return true;
  }
  const payload = profilePayloadFromSession(session);
  if (payload === null) {
    return false;
  }
  try {
    await saveProfile(payload);
    return true;
  } catch {
    return false;
  }
}

export function isValidPhone(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) {
    return true;
  }
  const digits = trimmed.replace(/\D/g, "");
  return /^[+0-9()\s-]+$/.test(trimmed) && digits.length >= 7 && digits.length <= 15;
}

export function normalizeCountryCode(value: string): string | null {
  const trimmed = value.trim().toUpperCase();
  if (!trimmed) {
    return null;
  }
  return /^[A-Z]{2}$/.test(trimmed) ? trimmed : null;
}
