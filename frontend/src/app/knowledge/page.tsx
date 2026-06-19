"use client";
import { useState, useEffect, useCallback } from "react";

interface DocItem {
  id: number;
  title: string;
  content?: string;
  category: string;
  status: string;
  version: number;
  tags?: string[];
  updated_at: string;
}

interface VersionItem {
  version: number;
  operated_at: string;
  operated_by: string | null;
}

export default function KnowledgePage() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [viewingId, setViewingId] = useState<number | null>(null);
  const [viewingDoc, setViewingDoc] = useState<DocItem | null>(null);
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");

  // ─── Fetch ───

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (keyword) params.set("keyword", keyword);
      if (category) params.set("category", category);
      const res = await fetch(`http://localhost:8000/api/v1/knowledge/docs?${params}`);
      const data = await res.json();
      setDocs(data.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [keyword, category]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  // ─── CRUD ───

  const createDoc = async () => {
    if (!title || !content) return;
    await fetch("http://localhost:8000/api/v1/knowledge/docs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchant_id: "demo", title, content, tags: [], category: category || "general" }),
    });
    setTitle(""); setContent(""); setCategory("");
    fetchDocs();
  };

  const updateDoc = async (id: number) => {
    if (!title || !content) return;
    await fetch(`http://localhost:8000/api/v1/knowledge/docs/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content }),
    });
    setEditingId(null); setTitle(""); setContent("");
    fetchDocs();
  };

  const deleteDoc = async (id: number) => {
    if (!confirm("确定要删除此文档？（软删除，可恢复）")) return;
    await fetch(`http://localhost:8000/api/v1/knowledge/docs/${id}`, { method: "DELETE" });
    fetchDocs();
  };

  const startEdit = (doc: DocItem) => {
    setEditingId(doc.id);
    setTitle(doc.title);
    // Need full content — fetch detail
    fetch(`http://localhost:8000/api/v1/knowledge/docs/${doc.id}`)
      .then(r => r.json())
      .then(d => setContent(d.content || ""));
  };

  const viewDoc = async (docId: number) => {
    setViewingId(docId);
    const [docRes, verRes] = await Promise.all([
      fetch(`http://localhost:8000/api/v1/knowledge/docs/${docId}`),
      fetch(`http://localhost:8000/api/v1/knowledge/docs/${docId}/versions`),
    ]);
    setViewingDoc(await docRes.json());
    setVersions((await verRes.json()).data || []);
  };

  // ─── Render ───

  const statusColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600",
    published: "bg-green-100 text-green-600",
    archived: "bg-red-100 text-red-600",
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">📄 知识文档管理</h1>

      {/* Filter bar */}
      <div className="flex gap-3 flex-wrap items-center">
        <input placeholder="搜索关键词..." value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchDocs()}
          className="px-3 py-1.5 border rounded text-sm w-48" />
        <input placeholder="分类筛选..." value={category}
          onChange={e => setCategory(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchDocs()}
          className="px-3 py-1.5 border rounded text-sm w-32" />
        <button onClick={fetchDocs}
          className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600">
          搜索
        </button>
        <span className="text-xs text-gray-400 ml-auto">{docs.length} 篇文档</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* ── Create / Edit Form ── */}
        <div className="bg-white rounded-lg border p-4 space-y-3">
          <h2 className="font-semibold text-sm">
            {editingId ? `编辑文档 #${editingId}` : "新建文档"}
          </h2>
          <input placeholder="文档标题" value={title}
            onChange={e => setTitle(e.target.value)}
            className="w-full px-3 py-1.5 border rounded text-sm" />
          <textarea placeholder="文档内容（支持 Markdown）" value={content}
            onChange={e => setContent(e.target.value)} rows={8}
            className="w-full px-3 py-1.5 border rounded text-sm font-mono" />
          <div className="flex gap-2">
            <button onClick={editingId ? () => updateDoc(editingId) : createDoc}
              disabled={!title || !content}
              className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50">
              {editingId ? "更新文档" : "创建文档"}
            </button>
            {editingId && (
              <button onClick={() => { setEditingId(null); setTitle(""); setContent(""); }}
                className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">
                取消
              </button>
            )}
          </div>
        </div>

        {/* ── Document List ── */}
        <div className="bg-white rounded-lg border p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm">文档列表</h2>
            <button onClick={fetchDocs}
              className="text-xs text-blue-500 hover:underline">刷新</button>
          </div>
          {loading ? (
            <div className="text-center text-gray-400 text-sm py-8">加载中...</div>
          ) : docs.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-8">暂无文档，请先创建</div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {docs.map((doc) => {
                const color = statusColors[doc.status] || "bg-gray-100";
                return (
                  <div key={doc.id} className="p-2 bg-gray-50 rounded text-sm flex items-start justify-between group">
                    <div className="min-w-0 flex-1">
                      <button onClick={() => viewDoc(doc.id)}
                        className="font-medium text-left hover:text-blue-600 truncate block w-full">
                        {doc.title}
                      </button>
                      <div className="text-xs text-gray-400 mt-0.5">
                        v{doc.version} · <span className={`px-1 py-0.5 rounded text-xs ${color}`}>{doc.status}</span>
                        {" · "}{doc.updated_at?.slice(0, 10)}
                      </div>
                    </div>
                    <div className="flex gap-1 ml-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      <button onClick={() => startEdit(doc)}
                        className="text-xs text-blue-500 hover:underline">编辑</button>
                      <button onClick={() => deleteDoc(doc.id)}
                        className="text-xs text-red-500 hover:underline">删除</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Detail / Version History Modal ── */}
      {viewingId && viewingDoc && (
        <div className="bg-white rounded-lg border p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">📖 {viewingDoc.title}</h2>
            <button onClick={() => setViewingId(null)}
              className="text-sm text-gray-400 hover:text-gray-600">✕ 关闭</button>
          </div>
          <div className="text-xs text-gray-400 space-x-3">
            <span>分类: {viewingDoc.category}</span>
            <span>版本: v{viewingDoc.version}</span>
            <span>状态: {viewingDoc.status}</span>
          </div>
          <pre className="bg-gray-50 rounded p-3 text-sm whitespace-pre-wrap font-sans">
            {viewingDoc.content}
          </pre>

          {/* Version history */}
          {versions.length > 0 && (
            <div className="border-t pt-3">
              <h3 className="text-sm font-medium mb-2">版本历史</h3>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {versions.map((v) => (
                  <div key={v.version} className="flex items-center justify-between text-xs text-gray-500 py-1 border-b border-gray-100">
                    <span className="font-mono">v{v.version}</span>
                    <span>{v.operated_at?.slice(0, 19).replace("T", " ")}</span>
                    <span>{v.operated_by || "系统"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Schema info */}
      <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
        <p><strong>数据模型：</strong></p>
        <p>· 支持 <strong>全文检索</strong>（PostgreSQL LIKE 双字段匹配）</p>
        <p>· 支持 <strong>版本管理</strong>（PUT 自动 version+1，创建快照到 knowledge_doc_versions）</p>
        <p>· 支持 <strong>软删除</strong>（DELETE 设置 deleted_at，列表自动过滤）</p>
        <p>· 支持 <strong>分类/标签</strong> 多维度筛选</p>
      </div>
    </div>
  );
}
