// ── Data shapes for pre-baked JSON files ────────────────────────────────

export interface Company {
  hk_ticker: string;
  company_name_en: string;
  listing_date: string | null;
  document_date: string | null;
  industry_primary: string | null;
  industry_source: string | null;
  total_net_proceeds: number | null;
  currency: string;
  needs_human_review: boolean;
}

export interface CompaniesData {
  companies: Company[];
  count: number;
}

export interface SankeyNode {
  name: string;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
  total_net_proceeds: number;
}

export interface TaxonomyData {
  categories: Record<string, Record<string, string[]>>;
  parent_order: string[];
}

export interface TimeSeriesPoint {
  year: string;
  Growth?: number;
  Financing?: number;
  "Working Capital"?: number;
  Others?: number;
}

export interface IndustryData {
  [industry: string]: {
    companies: number;
    parents: Record<string, number>;
  };
}

export interface GeoData {
  [geo: string]: {
    total_hkd_million: number;
    companies: number;
    /** Parent-category breakdown per geo region */
    parents: Record<string, number>;
  };
}

export interface CrossDimRow {
  hk_ticker: string;
  industry: string | null;
  listing_date: string | null;
  total_net_proceeds: number | null;
  use_id: string;
  parent_category: string;
  percentage: number;
  amount_hkd_million: number;
  /** Comma-separated ISO 2-letter country codes (from L5 country enrichment) */
  countries: string | null;
  /** Geographic scope: domestic_hk | mainland | overseas */
  geo: string | null;
  /** Commitment: committed | discretionary */
  commitment: string | null;
  /** Specificity: specific | general | vague */
  specificity: string | null;
  /** Deployment timeline: 0-12m | 12-24m | 24-36m | 36m+ | unspecified */
  timeline: string | null;
  /** Capital vs operating expenditure: capex | opex | financial */
  capex_opex: string | null;
  /** ESG tag: green | social | governance | null if absent */
  esg_tag: string | null;
}

export interface Manifest {
  generated_at: string;
  schema_version: string;
  company_count: number;
  taxonomy_sha: string;
}
