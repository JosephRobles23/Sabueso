import type {
  Country,
  Entity,
  Investigation,
  InvestigationEvent,
  InvestigationStatus,
} from "@sabueso/shared-types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`API ${status}: ${body}`);
    this.name = "ApiError";
  }
}

export interface SearchHit {
  id: string;
  name: string;
  identifier: string | null;
  country: Country;
  type: Entity["type"];
  highlight?: string;
}

export interface SearchResponse {
  hits: SearchHit[];
  took_ms: number;
}

export interface InvestigationSummary {
  id: string;
  target_name: string;
  status: InvestigationStatus;
  progress_pct: number;
  started_at: string;
  lead_count: number;
}

export const api = {
  search(query: string, country: Country = "pe", signal?: AbortSignal): Promise<SearchResponse> {
    const params = new URLSearchParams({ q: query, country });
    return request(`/api/v1/search?${params}`, { signal });
  },

  getInvestigation(id: string, signal?: AbortSignal): Promise<Investigation> {
    return request(`/api/v1/investigations/${id}`, { signal });
  },

  listRecent(signal?: AbortSignal): Promise<InvestigationSummary[]> {
    return request("/api/v1/investigations?limit=12", { signal });
  },

  createInvestigation(input: {
    target_query: string;
    country: Country;
  }): Promise<{ id: string }> {
    return request("/api/v1/investigations", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },
};

export function buildSseUrl(investigationId: string, lastEventId?: string | null) {
  const url = new URL(`${API_BASE}/api/v1/investigations/${investigationId}/events`);
  if (lastEventId) url.searchParams.set("last_event_id", lastEventId);
  return url.toString();
}

export type { Investigation, InvestigationEvent };
