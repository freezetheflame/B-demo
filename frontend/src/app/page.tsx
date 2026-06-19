"use client";
import { useEffect, useState } from "react";

interface MetricData {
  total_submits: number;
  success_count: number;
  fail_count: number;
  success_rate: number;
  avg_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
}

export default function Home() {
  const [health, setHealth] = useState<string>("检查中...");
  const [metrics, setMetrics] = useState<MetricData | null>(null);

  useEffect(() => {
    // Check backend health
    fetch("http://localhost:8000/health")
      .then(r => r.json())
      .then(d => setHealth(d.status))
      .catch(() => setHealth("未连接"));

    // Fetch real analytics metrics
    fetch("http://localhost:8000/api/v1/analytics/submit-metrics")
      .then(r => r.json())
      .then(d => setMetrics(d))
      .catch(() => {});
  }, []);

  const stats = [
    { label: "商户表单", value: "10,000", color: "bg-blue-500", desc: "模拟数据" },
    { label: "房源表单", value: "5,000", color: "bg-green-500", desc: "模拟数据" },
    { label: "商品表单", value: "5,000", color: "bg-purple-500", desc: "模拟数据" },
    { label: "报表表单", value: "—", color: "bg-amber-500", desc: "待扩展" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">B端企业入驻管理系统</h1>
          <p className="text-sm text-gray-500 mt-1">企业表单提交 · 地理聚合 · 批处理 · 数据统计</p>
        </div>
        <span className={`text-sm px-3 py-1 rounded-full ${
          health === "ok" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
        }`}>
          后端 {health === "ok" ? "已连接" : health}
        </span>
      </div>

      {/* Real-time Performance Metrics */}
      {metrics && (
        <div className="bg-gray-900 text-white rounded-lg p-4">
          <div className="text-xs text-gray-400 mb-2">表单提交实时指标</div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <div className="text-2xl font-mono font-bold text-blue-400">{metrics.total_submits.toLocaleString()}</div>
              <div className="text-xs text-gray-400">总提交</div>
            </div>
            <div>
              <div className="text-2xl font-mono font-bold text-green-400">{metrics.success_count.toLocaleString()}</div>
              <div className="text-xs text-gray-400">成功</div>
            </div>
            <div>
              <div className="text-2xl font-mono font-bold text-red-400">{metrics.fail_count.toLocaleString()}</div>
              <div className="text-xs text-gray-400">失败</div>
            </div>
            <div>
              <div className="text-2xl font-mono font-bold text-yellow-400">{metrics.success_rate}%</div>
              <div className="text-xs text-gray-400">成功率</div>
            </div>
            <div>
              <div className="text-2xl font-mono font-bold text-purple-400">{metrics.avg_duration_ms}ms</div>
              <div className="text-xs text-gray-400">平均耗时</div>
            </div>
          </div>
        </div>
      )}

      {/* Data Volume Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-lg shadow-sm p-4 border border-gray-100">
            <div className={`w-2 h-8 rounded ${s.color} mb-2`} />
            <div className="text-2xl font-bold">{s.value}</div>
            <div className="text-sm text-gray-500">{s.label}</div>
            <div className="text-xs text-gray-400 mt-1">{s.desc}</div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <a href="/forms" className="block bg-white rounded-lg shadow-sm p-4 border border-gray-100 hover:shadow-md hover:border-blue-200 transition-all">
          <h3 className="font-semibold mb-1">📋 表单管理</h3>
          <p className="text-sm text-gray-500">四类表单(商户/房源/商品/报表)CRUD + 多维度查询过滤器 + 批处理</p>
          <div className="mt-2 text-xs text-blue-500">10w+ 数据虚拟滚动渲染 →</div>
        </a>
        <a href="/aggregation" className="block bg-white rounded-lg shadow-sm p-4 border border-gray-100 hover:shadow-md hover:border-green-200 transition-all">
          <h3 className="font-semibold mb-1">📍 地理聚合</h3>
          <p className="text-sm text-gray-500">Geohash + PostGIS GIST索引 两阶段聚合策略，批量处理入驻订单</p>
          <div className="mt-2 text-xs text-green-500">636 个聚类簇已就绪 →</div>
        </a>
        <a href="/analytics" className="block bg-white rounded-lg shadow-sm p-4 border border-gray-100 hover:shadow-md hover:border-purple-200 transition-all">
          <h3 className="font-semibold mb-1">📊 数据统计</h3>
          <p className="text-sm text-gray-500">提交成功率、耗时分布、失败原因分析、按小时趋势</p>
          <div className="mt-2 text-xs text-purple-500">49,695 条埋点数据分析 →</div>
        </a>
      </div>

      {/* Tech Stack */}
      <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-100">
        <h2 className="font-semibold mb-3 text-sm">技术架构</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="p-2 bg-gray-50 rounded">
            <div className="font-medium">Frontend</div>
            <div className="text-gray-400">Next.js + Zustand + TailwindCSS</div>
          </div>
          <div className="p-2 bg-gray-50 rounded">
            <div className="font-medium">Backend</div>
            <div className="text-gray-400">FastAPI + SQLAlchemy + WebSocket</div>
          </div>
          <div className="p-2 bg-gray-50 rounded">
            <div className="font-medium">Database</div>
            <div className="text-gray-400">PostgreSQL + PostGIS + Redis</div>
          </div>
          <div className="p-2 bg-gray-50 rounded">
            <div className="font-medium">GIS Engine</div>
            <div className="text-gray-400">Geohash + GIST Index + DBSCAN</div>
          </div>
        </div>
      </div>
    </div>
  );
}
