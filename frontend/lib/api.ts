// All calls go through the Next.js rewrite (/api/* -> FastAPI), so same-origin, no CORS.
const BASE = "/api";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, { cache: "no-store", ...init });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

import type {
  Dashboard, DocumentRow, Partner, PartnerPrice, SearchResult, Service, ServicePrice, Unmatched,
} from "./types";

export const api = {
  dashboard: () => j<Dashboard>("/dashboard/stats"),
  search: (q: string) => j<SearchResult>(`/search?q=${encodeURIComponent(q)}`),

  services: (params: { q?: string; category?: string; limit?: number } = {}) => {
    const u = new URLSearchParams();
    if (params.q) u.set("q", params.q);
    if (params.category) u.set("category", params.category);
    u.set("limit", String(params.limit ?? 100));
    return j<Service[]>(`/services?${u}`);
  },
  servicePartners: (id: string) => j<PartnerPrice[]>(`/services/${id}/partners`),

  partners: (params: { city?: string } = {}) => {
    const u = new URLSearchParams();
    if (params.city) u.set("city", params.city);
    u.set("limit", "500");
    return j<Partner[]>(`/partners?${u}`);
  },
  partnerServices: (id: string, limit = 500) => j<ServicePrice[]>(`/partners/${id}/services?limit=${limit}`),

  documents: () => j<DocumentRow[]>("/documents?limit=500"),
  document: (id: string) => j<DocumentRow>(`/documents/${id}`),

  unmatched: (limit = 50) => j<Unmatched[]>(`/unmatched?limit=${limit}`),
  bulkAccept: (minScore: number, dryRun: boolean) =>
    j<{ eligible: number; accepted: number; min_score: number; dry_run: boolean }>(
      `/review/bulk-accept?min_score=${minScore}&dry_run=${dryRun}`,
      { method: "POST" }
    ),
  match: (body: { item_id: string; service_id?: string; create_name?: string; category?: string; decided_by?: string; note?: string }) =>
    j<{ item_id: string; service_id: string; action: string }>("/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  upload: (file: File, asynchronous = false) => {
    const fd = new FormData();
    fd.append("file", file);
    return j<{ created: string[]; skipped_duplicates: number; queued: boolean }>(
      `/upload?asynchronous=${asynchronous}`,
      { method: "POST", body: fd }
    );
  },
};

export function fmtKzt(v: string | number): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n) + " ₸";
}
