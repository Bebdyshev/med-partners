export type Tier = {
  tier_type: string;
  label_raw: string | null;
  amount_kzt: string;
  currency_original: string;
};

export type Service = { id: string; canonical_name: string; category: string | null; icd_code?: string | null };

export type Partner = {
  id: string; code: string; display_name: string;
  legal_name: string | null; city: string | null; is_active: boolean;
};

export type PartnerPrice = {
  partner_id: string; partner_name: string; city: string | null;
  raw_name: string; effective_date: string | null; tiers: Tier[]; is_verified: boolean;
};

export type ServicePrice = {
  service_id: string | null; raw_name: string; category: string | null;
  match_status: string; effective_date: string | null; tiers: Tier[];
};

export type DocumentRow = {
  id: string; partner_id: string; source_filename: string; file_format: string;
  status: string; year: number | null; parsed_at: string | null;
  method_summary: Record<string, number>; warnings: unknown[];
};

export type Suggestion = { service_id: string; canonical_name: string; score: number };
export type Unmatched = {
  item_id: string; raw_name: string; raw_code?: string | null; raw_category: string | null; partner_id: string;
  partner_name?: string | null; document_id?: string | null; source_filename?: string | null;
  file_format?: string | null; year?: number | null; source_ref?: string | null;
  match_status: string; match_score: number | null; extraction_method: string | null;
  tiers: Tier[]; suggestions: Suggestion[];
};

export type AiCompare = {
  choice: number; confidence: number; reason: string;
  best: { service_id: string; canonical_name: string; score: number } | null;
  candidates: Suggestion[];
};

export type DocPreview = {
  kind: "table" | "unsupported";
  label?: string; target?: number;
  rows?: { n: number; cells: string[] }[];
  error?: string;
};

export type ServiceDescription = {
  slug?: string;
  canonical_name: string;
  canonical_name_pattern?: string;
  short?: string;
  what?: string;
  why?: string;
  prep?: string;
  duration_min?: number;
  category?: string;
  found: boolean;
};

export type SearchResult = {
  services: { id: string; canonical_name: string; category: string | null; rank: number }[];
  partners: { id: string; display_name: string; city: string | null }[];
};

export type Dashboard = {
  documents: Record<string, number>;
  documents_total: number;
  items_total: number;
  items_active: number;
  services_in_dictionary: number;
  normalization: { auto: number; review: number; unmatched: number; manual: number; auto_match_pct: number };
  flagged_for_validation: number;
};

export type DocBreakdown = {
  id: string; source_filename: string; partner_name: string | null;
  file_format: string; status: string; year: number | null; parsed_at: string | null;
  items: number; auto: number; review: number; unmatched: number; manual: number;
  flagged: number; methods: Record<string, number>;
};
export type DashboardDocs = {
  documents: DocBreakdown[];
  by_method: Record<string, number>;
  by_category: { category: string; items: number }[];
};

export type PartnerBreakdown = {
  id: string; code: string; display_name: string; legal_name: string | null; city: string | null;
  is_active: boolean; items: number; auto: number; review: number; unmatched: number;
  auto_pct: number; documents: number; latest_year: number | null; formats: string[];
};
export type DashboardPartners = {
  partners: PartnerBreakdown[];
  totals: { partners: number; active: number; items: number; avg_auto_pct: number; with_pricelist: number };
};

export const TIER_LABELS: Record<string, string> = {
  base_no_vat: "Без НДС",
  resident_kzt: "Граждане РК",
  near_abroad: "СНГ / ближнее",
  far_abroad: "Дальнее зар.",
  nonresident_generic: "Нерезидент",
  unknown: "—",
};
