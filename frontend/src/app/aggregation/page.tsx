"use client";
import { useState } from "react";

export default function AggregationPage() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runAggregation = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/aggregation/run?distance_m=500&precision=6");
      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setResult({ error: e.message });
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">📍 地理坐标批量聚合</h1>

      <div className="bg-white rounded-lg border p-4 space-y-4">
        <p className="text-sm text-gray-600">
          基于 <strong>Geohash粗分桶</strong> + <strong>DBSCAN细聚类</strong> 的两阶段聚合策略，
          对已提交的商户表单按最近距离自动分组。
        </p>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-gray-500">聚合距离(米)</label>
            <input defaultValue={500} className="w-full px-2 py-1 border rounded text-sm" />
          </div>
          <div>
            <label className="text-xs text-gray-500">Geohash精度</label>
            <input defaultValue={6} className="w-full px-2 py-1 border rounded text-sm" />
          </div>
          <div className="flex items-end">
            <button
              onClick={runAggregation}
              disabled={loading}
              className="w-full px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
            >
              {loading ? "聚合中..." : "执行聚合"}
            </button>
          </div>
        </div>

        {result && (
          <div className="bg-gray-50 rounded p-3 text-sm space-y-1">
            {result.error ? (
              <p className="text-red-600">错误: {result.error}</p>
            ) : (
              <>
                <p>✅ 聚合完成</p>
                <p>处理表单: <strong>{result.total_forms}</strong> 条</p>
                <p>生成聚类: <strong>{result.clusters}</strong> 个</p>
                <p>耗时: <strong>{result.elapsed_seconds}</strong> 秒</p>
              </>
            )}
          </div>
        )}
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
        <strong>优化策略：</strong>
        ① PostGIS GIST空间索引 → O(n)到O(log n) |
        ② Geohash前缀过滤 → 减少90%计算量 |
        ③ 增量聚合 → O(n²)到O(n log n) |
        ④ Redis缓存结果 → 重复查询直接命中
      </div>
    </div>
  );
}
