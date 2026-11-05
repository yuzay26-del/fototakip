import createClient from "openapi-fetch";

import type { components, paths } from "@/api/schema";

export type HealthResponse = components["schemas"]["HealthResponse"];

// fetch her çağrıda okunur; testlerde globalThis.fetch değiştirilebilsin diye.
export const api = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  fetch: (request) => globalThis.fetch(request),
});

export async function getHealth(): Promise<HealthResponse> {
  const { data, error } = await api.GET("/health");
  if (error || !data) throw new Error("Sunucuya ulaşılamadı");
  return data;
}
