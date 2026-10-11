export type AssistantStatus = "available" | "in_development";

export interface AssistantCatalogueEntry {
  id: string;
  name: string;
  description: string;
  status: AssistantStatus;
  capabilities: string[];
  launch_url: string | null;
  repository_url: string;
  app_path: string | null;
}

export interface AssistantCatalogueResponse {
  success: boolean;
  message: string;
  data: AssistantCatalogueEntry[];
}

import { API_URL, errorMessage } from "./api";

export async function fetchCatalogue(): Promise<AssistantCatalogueEntry[]> {
  const response = await fetch(`${API_URL}/api/v1/assistants`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  const body = (await response.json()) as AssistantCatalogueResponse;
  return body.data;
}

export async function fetchAssistantById(
  assistantId: string,
): Promise<AssistantCatalogueEntry | null> {
  const catalogue = await fetchCatalogue();
  return catalogue.find((assistant) => assistant.id === assistantId) ?? null;
}
