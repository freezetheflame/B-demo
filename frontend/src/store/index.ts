import { create } from "zustand";

// ─── Types ───

export interface FormRow {
  id: number;
  status: string;
  name?: string;
  title?: string;
  address?: string;
  category?: string;
  contact_name?: string;
  area?: number;
  price?: number;
  sku?: string;
  stock?: number;
  [key: string]: unknown;
}

interface CacheEntry {
  data: FormRow[];
  total: number;
}

interface FormStore {
  // ── State (Model) ──
  formType: string;
  page: number;
  pageSize: number;
  keyword: string;
  filterStatus: string;
  rows: FormRow[];
  total: number;
  loading: boolean;
  error: string | null;
  cache: Map<string, CacheEntry>;

  // ── Computed (ViewModel) ──
  totalPages: () => number;
  cacheSize: () => number;

  // ── Actions ──
  setType: (t: string) => void;
  setPage: (p: number) => void;
  setKeyword: (kw: string) => void;
  setFilterStatus: (st: string) => void;
  fetchForms: () => Promise<void>;
  batchProcess: (ids: number[]) => Promise<void>;
  invalidateCache: () => void;
}

const CACHE_MAX = 50;

export const useFormStore = create<FormStore>((set, get) => ({
  formType: "merchant",
  page: 1,
  pageSize: 100,
  keyword: "",
  filterStatus: "",
  rows: [],
  total: 0,
  loading: false,
  error: null,
  cache: new Map(),

  totalPages: () => Math.ceil(get().total / get().pageSize),
  cacheSize: () => get().cache.size,

  setType: (t) => set({ formType: t, page: 1 }),
  setPage: (p) => { set({ page: p }); get().fetchForms(); },
  setKeyword: (kw) => set({ keyword: kw, page: 1 }),
  setFilterStatus: (st) => set({ filterStatus: st, page: 1 }),

  fetchForms: async () => {
    const { formType, page, pageSize, keyword, filterStatus, cache } = get();
    const cacheKey = `${formType}:${page}:${keyword}:${filterStatus}`;
    const cached = cache.get(cacheKey);
    if (cached) {
      set({ rows: cached.data, total: cached.total, loading: false });
      return;
    }

    set({ loading: true, error: null });
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (keyword) params.set("keyword", keyword);
      if (filterStatus) params.set("status", filterStatus);
      const res = await fetch(`http://localhost:8000/api/v1/forms/${formType}?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const newCache = new Map(cache);
      newCache.set(cacheKey, { data: data.data || [], total: data.total || 0 });
      if (newCache.size > CACHE_MAX) {
        const firstKey = newCache.keys().next().value;
        if (firstKey) newCache.delete(firstKey);
      }

      set({ rows: data.data || [], total: data.total || 0, cache: newCache, loading: false });
    } catch (e: any) {
      set({ error: e.message, rows: [], total: 0, loading: false });
    }
  },

  batchProcess: async (ids) => {
    const { formType } = get();
    try {
      const res = await fetch(`http://localhost:8000/api/v1/forms/${formType}/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ids),
      });
      if (res.ok) {
        get().invalidateCache();
        await get().fetchForms();
      }
    } catch (e: any) {
      set({ error: `批处理失败: ${e.message}` });
    }
  },

  invalidateCache: () => set({ cache: new Map() }),
}));
