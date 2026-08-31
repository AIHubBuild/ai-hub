export type AssistantStatus = "available" | "in_development";

export interface AssistantCatalogueEntry {
  id: string;
  name: string;
  description: string;
  status: AssistantStatus;
  capabilities: string[];
  launch_url: string | null;
  repository_url: string;
}

export interface AssistantCatalogueResponse {
  success: boolean;
  message: string;
  data: AssistantCatalogueEntry[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchCatalogue(): Promise<AssistantCatalogueEntry[]> {
  const response = await fetch(`${API_URL}/api/v1/assistants`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Catalogue request failed with status ${response.status}`);
  }
  const body = (await response.json()) as AssistantCatalogueResponse;
  return body.data;
}
