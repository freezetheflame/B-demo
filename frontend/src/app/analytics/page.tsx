"use client";
import { useState } from "react";

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/analytics/submit-metrics?start=2026-01-01&end=2026-12-31");
      const data = await res.json();
      setMetrics(data);
    } catch (e: any) {
      setMetrics({ error: e.message });
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">📊 表单提交数据统计</h1>

      <div className="bg-white rounded-lg border p-4 space-y-4">
        <p className="text-sm text-gray-600">
          统计企业方各类表单的提交成功率、耗时分布与失败原因。
          埋点数据通过 <code className="bg-gray-100 px-1 rounded">POST /api/v1/analytics/log</code> 实时记录。
        </p>

        <button
          onClick={fetchMetrics}
          disabled={loading}
          className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? "加载中..." : "获取统计数据"}
        </button>

        {metrics && (
          <div className="space-y-4">
            {metrics.error ? (
              <p className="text-red-600 text-sm">错误: {metrics.error}</p>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="bg-gray-50 rounded p-3 text-center">
                    <div className="text-2xl font-bold text-blue-600">{metrics.total_submits}</div>
                    <div className="text-xs text-gray-500">总提交</div>
                  </div>
                  <div className="bg-gray-50 rounded p-3 text-center">
                    <div className="text-2xl font-bold text-green-600">{metrics.success_count}</div>
                    <div className="text-xs text-gray-500">成功</div>
                  </div>
                  <div className="bg-gray-50 rounded p-3 text-center">
                    <div className="text-2xl font-bold text-red-600">{metrics.fail_count}</div>
                    <div className="text-xs text-gray-500">失败</div>
                  </div>
                  <div className="bg-gray-50 rounded p-3 text-center">
                    <div className="text-2xl font-bold text-purple-600">{metrics.success_rate}%</div>
                    <div className="text-xs text-gray-500">成功率</div>
                  </div>
                  <div className="bg-gray-50 rounded p-3 text-center">
                    <div className="text-2xl font-bold text-amber-600">{metrics.avg_duration_ms}ms</div>
                    <div className="text-xs text-gray-500">平均耗时</div>
                  </div>
                </div>

                {metrics.fail_reasons && Object.keys(metrics.fail_reasons).length > 0 && (
                  <div>
                    <h3 className="font-semibold text-sm mb-2">失败原因分布</h3>
                    <div className="space-y-1">
                      {Object.entries(metrics.fail_reasons).map(([code, count]) => (
                        <div key={code} className="flex items-center gap-2 text-sm">
                          <span className="bg-red-100 text-red-700 px-2 rounded text-xs">{code}</span>
                          <div className="flex-1 bg-gray-100 rounded h-4">
                            <div className="bg-red-400 rounded h-4" style={{ width: `${(count as number) / metrics.fail_count * 100}%` }} />
                          </div>
                          <span className="text-xs text-gray-500">{String(count)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {metrics.hourly_trend && metrics.hourly_trend.length > 0 && (
                  <div>
                    <h3 className="font-semibold text-sm mb-2">按小时趋势（近24h）</h3>
                    <div className="grid grid-cols-24 gap-0.5 h-16 items-end">
                      {metrics.hourly_trend.slice(-24).map((h: any, i: number) => (
                        <div key={i} className="flex flex-col items-center">
                          <div
                            className="w-full bg-blue-400 rounded-t"
                            style={{ height: `${h.total / Math.max(...metrics.hourly_trend.slice(-24).map((x: any) => x.total)) * 60}px` }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
