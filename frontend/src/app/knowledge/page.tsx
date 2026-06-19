"use client";
import { useState } from "react";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/knowledge/docs?page=1&page_size=20");
      const data = await res.json();
      setDocs(data.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const createDoc = async () => {
    if (!title || !content) return;
    try {
      await fetch("http://localhost:8000/api/v1/knowledge/docs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchant_id: "demo", title, content, tags: [] }),
      });
      setTitle(""); setContent("");
      fetchDocs();
    } catch (e) { console.error(e); }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">📄 知识文档管理</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Create */}
        <div className="bg-white rounded-lg border p-4 space-y-3">
          <h2 className="font-semibold text-sm">新建文档</h2>
          <input
            placeholder="文档标题"
            value={title}
            onChange={e => setTitle(e.target.value)}
            className="w-full px-3 py-1.5 border rounded text-sm"
          />
          <textarea
            placeholder="文档内容（支持 Markdown）"
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={6}
            className="w-full px-3 py-1.5 border rounded text-sm"
          />
          <button
            onClick={createDoc}
            className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
          >
            创建文档
          </button>
        </div>

        {/* List */}
        <div className="bg-white rounded-lg border p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm">文档列表</h2>
            <button
              onClick={fetchDocs}
              className="text-xs text-blue-500 hover:underline"
            >
              刷新
            </button>
          </div>
          {loading ? (
            <div className="text-center text-gray-400 text-sm py-8">加载中...</div>
          ) : docs.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-8">
              暂无文档，请先创建
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {docs.map((doc: any) => (
                <div key={doc.id} className="p-2 bg-gray-50 rounded text-sm">
                  <div className="font-medium">{doc.title}</div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    v{doc.version} · {doc.status} · {doc.updated_at?.slice(0, 10)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Doc Schema Info */}
      <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
        <p><strong>数据模型：</strong></p>
        <p>· 支持 <strong>全文检索</strong>（PostgreSQL TSVector / Elasticsearch）</p>
        <p>· 支持 <strong>版本管理</strong>（自动记录变更历史，可回滚）</p>
        <p>· 支持 <strong>软删除</strong>（deleted_at 字段，数据可恢复）</p>
        <p>· 支持 <strong>分类/标签</strong> 多维度筛选</p>
      </div>
    </div>
  );
}
