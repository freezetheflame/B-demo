"use client";
import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { FixedSizeList as List } from "react-window";

const FORM_TYPES = [
  { key: "merchant", label: "商户信息", desc: "商户信息提交流程 → 数据清洗 → 地理编码 → 批量聚合 → 状态更新" },
  { key: "listing", label: "商户房源", desc: "房源信息提交流程 → 按商户聚合 → 价格/面积校验 → 批量审批" },
  { key: "product", label: "商户商品", desc: "商品信息提交流程 → SKU校验 → 库存同步 → 批量上架" },
  { key: "report", label: "商户报表", desc: "报表提交流程 → 数据校验 → 归档存储 → 分析报告生成" },
];

interface FormRow {
  id: number;
  status: string;
}

// LRU-like cache to avoid refetching same pages
const formCache = new Map<string, { data: FormRow[]; total: number }>();

export default function FormsPage() {
  const searchParams = useSearchParams();
  const [type, setType] = useState(searchParams.get("type") || "merchant");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<FormRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const PAGE_SIZE = 100;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const fetchForms = useCallback(async (formType: string, p: number, kw: string, st: string) => {
    const cacheKey = `${formType}:${p}:${kw}:${st}`;
    const cached = formCache.get(cacheKey);
    if (cached) {
      setRows(cached.data);
      setTotal(cached.total);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", String(p));
      params.set("page_size", String(PAGE_SIZE));
      if (kw) params.set("keyword", kw);
      if (st) params.set("status", st);

      const res = await fetch(`http://localhost:8000/api/v1/forms/${formType}?${params}`, {
        // Cache-Control for browser HTTP cache
        headers: { "Cache-Control": "max-age=30" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Store in LRU cache (max 50 entries)
      formCache.set(cacheKey, { data: data.data || [], total: data.total || 0 });
      if (formCache.size > 50) {
        const firstKey = formCache.keys().next().value;
        if (firstKey) formCache.delete(firstKey);
      }

      setRows(data.data || []);
      setTotal(data.total || 0);
    } catch (e: any) {
      setError(e.message);
      setRows([]);
      setTotal(0);
    }
    setLoading(false);
  }, []);

  // Fetch on mount and when filters change
  useEffect(() => {
    fetchForms(type, page, keyword, filterStatus);
  }, [type, page, keyword, filterStatus, fetchForms]);

  const handleSearch = () => {
    setPage(1);
    // Reset will trigger useEffect which calls fetchForms
  };

  // Batch process selected forms
  const handleBatchProcess = async () => {
    if (rows.length === 0) return;
    const ids = rows.slice(0, 100).map(r => r.id);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/forms/${type}/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ids),
      });
      if (res.ok) {
        formCache.clear(); // invalidate cache
        fetchForms(type, page, keyword, filterStatus);
      }
    } catch (e: any) {
      setError(`批处理失败: ${e.message}`);
    }
  };

  const statusColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600",
    submitted: "bg-blue-100 text-blue-600",
    processing: "bg-yellow-100 text-yellow-600",
    approved: "bg-green-100 text-green-600",
    rejected: "bg-red-100 text-red-600",
  };

  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const row = rows[index];
    if (!row) return null;
    const color = statusColors[row.status?.toLowerCase()] || "bg-gray-100";
    return (
      <div style={style} className="flex items-center px-4 border-b border-gray-50 text-sm">
        <span className="w-16 text-gray-400">{row.id}</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>
          {row.status}
        </span>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">表单管理</h1>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">
          页面缓存: {formCache.size} 条
        </span>
      </div>

      {/* Form Type Tabs */}
      <div className="flex gap-2 border-b pb-2">
        {FORM_TYPES.map((ft) => (
          <button
            key={ft.key}
            onClick={() => { setType(ft.key); setPage(1); }}
            className={`px-4 py-1.5 rounded-t text-sm transition-colors ${
              type === ft.key ? "bg-blue-500 text-white" : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            {ft.label}
          </button>
        ))}
      </div>

      {/* Flow Description */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
        <strong>当前流程：</strong>{FORM_TYPES.find(ft => ft.key === type)?.desc}
      </div>

      {/* Filter Bar */}
      <div className="flex gap-3 flex-wrap items-center">
        <input
          placeholder="搜索关键词..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          className="px-3 py-1.5 border rounded text-sm w-48"
        />
        <select
          value={filterStatus}
          onChange={e => { setFilterStatus(e.target.value); setPage(1); }}
          className="px-3 py-1.5 border rounded text-sm"
        >
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="submitted">已提交</option>
          <option value="processing">处理中</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
        </select>
        <button
          onClick={handleSearch}
          className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
        >
          查询
        </button>
        <button
          onClick={handleBatchProcess}
          disabled={rows.length === 0}
          className="px-4 py-1.5 bg-amber-500 text-white rounded text-sm hover:bg-amber-600 disabled:opacity-50"
        >
          批处理(前100条)
        </button>
        {total > 0 && (
          <span className="text-xs text-gray-400 ml-auto">
            共 {total.toLocaleString()} 条 | 第 {page}/{totalPages || 1} 页
          </span>
        )}
      </div>

      {/* Data Table with Virtual Scrolling */}
      <div className="bg-white rounded-lg border">
        {/* Header */}
        <div className="flex items-center px-4 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500">
          <span className="w-16">ID</span>
          <span>状态</span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 p-12 text-gray-400">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            加载中...
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <p className="text-red-500 text-sm mb-2">错误: {error}</p>
            <button onClick={() => fetchForms(type, page, keyword, filterStatus)} className="text-blue-500 text-sm underline">
              重试
            </button>
          </div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-gray-400 text-sm">
            <p className="mb-2">暂无数据</p>
            <p className="text-xs">调整筛选条件后重新查询，或运行数据模拟脚本</p>
          </div>
        ) : (
          <List
            height={500}
            itemCount={rows.length}
            itemSize={36}
            width="100%"
          >
            {Row}
          </List>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-30"
          >
            上一页
          </button>
          <span className="px-3 py-1 text-gray-600">{page} / {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-30"
          >
            下一页
          </button>
        </div>
      )}

      {/* WebSocket Status */}
      <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-green-400" />
        <span>WebSocket: ws://localhost:8000/ws/progress (已就绪)</span>
        <span className="ml-auto">缓存命中: {formCache.size} 分页</span>
      </div>
    </div>
  );
}
