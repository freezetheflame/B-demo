/**
 * Pure utilities extracted from FormsPage — independently testable.
 */

export const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  submitted: "bg-blue-100 text-blue-600",
  processing: "bg-yellow-100 text-yellow-600",
  approved: "bg-green-100 text-green-600",
  rejected: "bg-red-100 text-red-600",
};

export function formatCell(key: string, val: unknown): string {
  if (val === null || val === undefined) return "-";
  if (key === "price") return `¥${Number(val).toLocaleString()}`;
  if (key === "area") return `${Number(val).toFixed(1)}`;
  if (key === "stock") return Number(val).toLocaleString();
  return String(val);
}

/**
 * LRU-like cache: Map-based with max-size eviction.
 * Oldest entry (first inserted) is evicted when size exceeds max.
 */
export function createFormCache(maxSize = 50) {
  const cache = new Map<string, { data: unknown[]; total: number }>();

  return {
    get(key: string) {
      return cache.get(key);
    },
    set(key: string, value: { data: unknown[]; total: number }) {
      cache.set(key, value);
      if (cache.size > maxSize) {
        const firstKey = cache.keys().next().value;
        if (firstKey) cache.delete(firstKey);
      }
    },
    clear() {
      cache.clear();
    },
    get size() {
      return cache.size;
    },
  };
}
