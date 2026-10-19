import { API_URL, ApiError, errorMessage } from "./api";
import { authHeaders } from "./supabase";

export type AdminWindow = "24h" | "7d" | "30d";
export type AssistantId = "resume_ats" | "support_copilot";
export type RequestStatus = "success" | "error";
export type IncidentStatus =
  | "open"
  | "investigating"
  | "waiting_for_information"
  | "resolved"
  | "closed";
export type IncidentPriority = "low" | "medium" | "high" | "critical";
export type EntitlementTier = "free" | "pro";

interface AdminEnvelope<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface AdminMeData {
  user_id: string;
  email: string | null;
}

export interface UsageAssistant {
  assistant: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  average_latency_ms: number | null;
}

export interface UsageData {
  window_start: string | null;
  window_end: string | null;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate: number;
  failure_rate: number;
  average_latency_ms: number | null;
  max_latency_ms: number | null;
  by_assistant: UsageAssistant[];
  token_usage_available: boolean;
}

export interface AdminRequestItem {
  run_id: string;
  user_id: string;
  assistant: string;
  workflow_id: string;
  model: string | null;
  status: RequestStatus;
  error_category: string | null;
  latency_ms: number;
  created_at: string | null;
}

export interface AdminRequestDetail extends AdminRequestItem {
  prompt_id: string | null;
  prompt_version: number | null;
  thread_id: string | null;
}

export interface RequestListData {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  items: AdminRequestItem[];
}

export interface AdminAuditItem {
  event_id: string;
  actor_user_id: string | null;
  admin_user_id: string | null;
  actor_is_admin: boolean;
  action: string;
  target_type: string;
  target_id: string | null;
  success: boolean;
  reason: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

export interface AuditListData {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  items: AdminAuditItem[];
}

export interface AdminIncidentItem {
  incident_id: string;
  linked_run_id: string | null;
  linked_user_id: string | null;
  title: string;
  category: string;
  priority: IncidentPriority;
  status: IncidentStatus;
  assigned_admin_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
}

export interface AdminIncidentDetail extends AdminIncidentItem {
  description: string;
  created_by: string;
  resolution_summary: string | null;
  history: AdminAuditItem[];
}

export interface IncidentListData {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  items: AdminIncidentItem[];
}

export interface ManualEntitlement {
  user_id: string;
  tier: EntitlementTier;
  limits: Record<string, unknown> | null;
  source: "manual";
  granted_by: string;
  reason: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface EntitlementListData {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  items: ManualEntitlement[];
}

interface AdminRequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT";
  params?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
}

function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): string {
  const url = new URL(`${API_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function adminRequest<T>(
  path: string,
  { method = "GET", params, body }: AdminRequestOptions = {},
): Promise<T> {
  const headers = await authHeaders();
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(buildUrl(path, params), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  const payload = (await response.json()) as AdminEnvelope<T>;
  if (!payload.success) {
    throw new ApiError(payload.message, response.status);
  }
  return payload.data;
}

function adminFetch<T>(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): Promise<T> {
  return adminRequest<T>(path, { params });
}

export function fetchAdminMe(): Promise<AdminMeData> {
  return adminFetch<AdminMeData>("/api/v1/admin/me");
}

export function fetchAdminUsage({
  window = "7d",
  assistant,
}: {
  window?: AdminWindow;
  assistant?: AssistantId | "";
} = {}): Promise<UsageData> {
  return adminFetch<UsageData>("/api/v1/admin/usage", {
    window,
    assistant: assistant || undefined,
  });
}

export function fetchAdminRequests({
  window = "30d",
  status,
  assistant,
  runId,
  userId,
  errorCategory,
  page = 1,
  pageSize = 25,
}: {
  window?: AdminWindow;
  status?: RequestStatus | "";
  assistant?: AssistantId | "";
  runId?: string;
  userId?: string;
  errorCategory?: string;
  page?: number;
  pageSize?: number;
} = {}): Promise<RequestListData> {
  return adminFetch<RequestListData>("/api/v1/admin/requests", {
    window,
    status: status || undefined,
    assistant: assistant || undefined,
    run_id: runId || undefined,
    user_id: userId || undefined,
    error_category: errorCategory || undefined,
    page,
    page_size: pageSize,
  });
}

export function fetchAdminRequest(
  runId: string,
): Promise<AdminRequestDetail> {
  return adminFetch<AdminRequestDetail>(
    `/api/v1/admin/requests/${encodeURIComponent(runId)}`,
  );
}

export function fetchAdminAudit({
  window = "30d",
  success,
  action,
  targetType,
  page = 1,
  pageSize = 25,
}: {
  window?: AdminWindow;
  success?: boolean;
  action?: string;
  targetType?: string;
  page?: number;
  pageSize?: number;
} = {}): Promise<AuditListData> {
  return adminFetch<AuditListData>("/api/v1/admin/audit", {
    window,
    success: success === undefined ? undefined : String(success),
    action: action || undefined,
    target_type: targetType || undefined,
    page,
    page_size: pageSize,
  });
}


export function fetchAdminIncidents({
  status,
  priority,
  page = 1,
  pageSize = 25,
}: {
  status?: IncidentStatus | "";
  priority?: IncidentPriority | "";
  page?: number;
  pageSize?: number;
} = {}): Promise<IncidentListData> {
  return adminFetch<IncidentListData>("/api/v1/admin/incidents", {
    status: status || undefined,
    priority: priority || undefined,
    page,
    page_size: pageSize,
  });
}

export function fetchAdminIncident(
  incidentId: string,
): Promise<AdminIncidentDetail> {
  return adminFetch<AdminIncidentDetail>(
    `/api/v1/admin/incidents/${encodeURIComponent(incidentId)}`,
  );
}

export function createAdminIncident(payload: {
  title: string;
  description: string;
  category: string;
  priority: IncidentPriority;
  linked_run_id?: string | null;
  linked_user_id?: string | null;
  assigned_admin_id?: string | null;
}): Promise<Omit<AdminIncidentDetail, "history">> {
  return adminRequest<Omit<AdminIncidentDetail, "history">>("/api/v1/admin/incidents", {
    method: "POST",
    body: payload,
  });
}

export function updateAdminIncident(
  incidentId: string,
  payload: {
    status?: IncidentStatus;
    priority?: IncidentPriority;
    assigned_admin_id?: string | null;
    resolution_summary?: string | null;
  },
): Promise<Omit<AdminIncidentDetail, "history">> {
  return adminRequest<Omit<AdminIncidentDetail, "history">>(
    `/api/v1/admin/incidents/${encodeURIComponent(incidentId)}`,
    { method: "PATCH", body: payload },
  );
}

export function fetchAdminEntitlements({
  tier,
  page = 1,
  pageSize = 25,
}: {
  tier?: EntitlementTier | "";
  page?: number;
  pageSize?: number;
} = {}): Promise<EntitlementListData> {
  return adminFetch<EntitlementListData>("/api/v1/admin/entitlements", {
    tier: tier || undefined,
    page,
    page_size: pageSize,
  });
}

export function fetchAdminEntitlement(
  userId: string,
): Promise<ManualEntitlement> {
  return adminFetch<ManualEntitlement>(
    `/api/v1/admin/users/${encodeURIComponent(userId)}/entitlement`,
  );
}

export function setAdminEntitlement(
  userId: string,
  payload: {
    tier: EntitlementTier;
    limits: Record<string, unknown> | null;
    reason: string;
  },
): Promise<ManualEntitlement> {
  return adminRequest<ManualEntitlement>(
    `/api/v1/admin/users/${encodeURIComponent(userId)}/entitlement`,
    { method: "PUT", body: payload },
  );
}
