/**
 * Frontend utility tests — formatCell, statusColors, LRU cache.
 *
 * Run:  npx vitest run
 */
import { describe, it, expect, beforeEach } from "vitest";
import { formatCell, statusColors, createFormCache } from "./utils";

// ═══════════════════════════════════════════════════════════════
// 功能点 7: formatCell — 前端数据格式化
// 测试不同字段的展示格式（价格、面积、库存、空值）
// ═══════════════════════════════════════════════════════════════

describe("formatCell", () => {
  it("formats price with ¥ symbol and thousands separator", () => {
    expect(formatCell("price", 15000)).toBe("¥15,000");
    expect(formatCell("price", 1234567)).toBe("¥1,234,567");
    expect(formatCell("price", 0)).toBe("¥0");
  });

  it("formats area to 1 decimal place", () => {
    expect(formatCell("area", 150)).toBe("150.0");
    expect(formatCell("area", 87.654)).toBe("87.7");
  });

  it("formats stock with thousands separator", () => {
    expect(formatCell("stock", 9999)).toBe("9,999");
    expect(formatCell("stock", 0)).toBe("0");
    expect(formatCell("stock", 1000000)).toBe("1,000,000");
  });

  it("returns '-' for null or undefined", () => {
    expect(formatCell("name", null)).toBe("-");
    expect(formatCell("address", undefined)).toBe("-");
  });

  it("returns string value as-is for unknown keys", () => {
    expect(formatCell("name", "商户_001")).toBe("商户_001");
    expect(formatCell("category", "餐饮")).toBe("餐饮");
    expect(formatCell("unknown_field", 42)).toBe("42");
  });
});

// ═══════════════════════════════════════════════════════════════
// 功能点 8: statusColors — 状态颜色映射
// 测试所有 5 种状态都有对应的颜色类
// ═══════════════════════════════════════════════════════════════

describe("statusColors", () => {
  it("has color for all 5 form statuses", () => {
    expect(statusColors).toHaveProperty("draft");
    expect(statusColors).toHaveProperty("submitted");
    expect(statusColors).toHaveProperty("processing");
    expect(statusColors).toHaveProperty("approved");
    expect(statusColors).toHaveProperty("rejected");
  });

  it("each color value is a non-empty Tailwind class string", () => {
    for (const [status, classes] of Object.entries(statusColors)) {
      expect(classes, `${status} should have color classes`).toBeTruthy();
      expect(classes, `${status} should contain bg-`).toContain("bg-");
      expect(classes, `${status} should contain text-`).toContain("text-");
    }
  });

  it("approved is green, rejected is red (semantic correctness)", () => {
    expect(statusColors.approved).toContain("green");
    expect(statusColors.rejected).toContain("red");
  });
});

// ═══════════════════════════════════════════════════════════════
// 功能点 9: LRU 缓存 — 表单分页缓存
// 测试缓存命中和驱逐策略
// ═══════════════════════════════════════════════════════════════

describe("createFormCache (LRU)", () => {
  let cache: ReturnType<typeof createFormCache>;

  beforeEach(() => {
    cache = createFormCache(3); // small max for eviction testing
  });

  it("stores and retrieves cached data", () => {
    cache.set("merchant:1:foo:", { data: [{ id: 1 }], total: 100 });
    const entry = cache.get("merchant:1:foo:");
    expect(entry).toBeDefined();
    expect(entry!.data).toEqual([{ id: 1 }]);
    expect(entry!.total).toBe(100);
  });

  it("returns undefined for cache miss", () => {
    expect(cache.get("nonexistent")).toBeUndefined();
  });

  it("evicts oldest entry when exceeding max size", () => {
    cache.set("key1", { data: [], total: 1 });
    cache.set("key2", { data: [], total: 2 });
    cache.set("key3", { data: [], total: 3 });
    expect(cache.size).toBe(3);

    // 4th insertion triggers eviction of key1 (oldest)
    cache.set("key4", { data: [], total: 4 });
    expect(cache.size).toBe(3);
    expect(cache.get("key1")).toBeUndefined();
    expect(cache.get("key4")).toBeDefined();
  });

  it("clear removes all entries", () => {
    cache.set("a", { data: [], total: 1 });
    cache.set("b", { data: [], total: 2 });
    cache.clear();
    expect(cache.size).toBe(0);
    expect(cache.get("a")).toBeUndefined();
  });

  it("does not evict when within size limit", () => {
    cache.set("a", { data: [], total: 1 });
    cache.set("b", { data: [], total: 2 });
    expect(cache.size).toBe(2);
    expect(cache.get("a")).toBeDefined();
  });

  it("different cache keys for same page with different filters", () => {
    cache.set("merchant:1:foo:submitted", { data: [{ id: 1 }], total: 1 });
    cache.set("merchant:1:foo:approved", { data: [{ id: 2 }], total: 1 });
    expect(cache.get("merchant:1:foo:submitted")!.data).toEqual([{ id: 1 }]);
    expect(cache.get("merchant:1:foo:approved")!.data).toEqual([{ id: 2 }]);
  });
});
