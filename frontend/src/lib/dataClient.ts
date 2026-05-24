import type {
  CompaniesData, SankeyData, TaxonomyData, TimeSeriesPoint,
  IndustryData, GeoData, CrossDimRow, Manifest,
} from './sharedTypes';

const BASE = './data';

class LRUCache<K, V> {
  private max: number;
  private cache: Map<K, V>;
  constructor(max: number) { this.max = max; this.cache = new Map(); }
  get(key: K): V | undefined {
    if (!this.cache.has(key)) return undefined;
    const val = this.cache.get(key)!;
    this.cache.delete(key); this.cache.set(key, val); // move to end
    return val;
  }
  set(key: K, val: V): void {
    if (this.cache.has(key)) this.cache.delete(key);
    else if (this.cache.size >= this.max) this.cache.delete(this.cache.keys().next().value!);
    this.cache.set(key, val);
  }
  has(key: K): boolean { return this.cache.has(key); }
  delete(key: K): void { this.cache.delete(key); }
  clear(): void { this.cache.clear(); }
  get size(): number { return this.cache.size; }
}

const cache = new LRUCache<string, unknown>(50);

async function fetchJSON<T>(filename: string): Promise<T> {
  if (cache.has(filename)) {
    return cache.get(filename) as T;
  }
  const resp = await fetch(`${BASE}/${filename}`);
  if (!resp.ok) throw new Error(`Failed to fetch ${filename}: ${resp.status}`);
  const data = (await resp.json()) as T;
  cache.set(filename, data);
  return data;
}

export async function fetchManifest(): Promise<Manifest> {
  return fetchJSON<Manifest>('manifest.json');
}

export async function fetchCompanies(): Promise<CompaniesData> {
  return fetchJSON<CompaniesData>('companies.json');
}

export async function fetchTaxonomy(): Promise<TaxonomyData> {
  return fetchJSON<TaxonomyData>('taxonomy.json');
}

export async function fetchTimeSeries(): Promise<TimeSeriesPoint[]> {
  return fetchJSON<TimeSeriesPoint[]>('time_series.json');
}

export async function fetchByIndustry(): Promise<IndustryData> {
  return fetchJSON<IndustryData>('by_industry.json');
}

export async function fetchByGeo(): Promise<GeoData> {
  return fetchJSON<GeoData>('by_geo.json');
}

export async function fetchCrossDim(): Promise<CrossDimRow[]> {
  return fetchJSON<CrossDimRow[]>('cross_dim.json');
}

export async function fetchSankey(ticker: string): Promise<SankeyData> {
  return fetchJSON<SankeyData>(`sankey/${ticker}.json`);
}

export function clearCache(): void {
  cache.clear();
}
