import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BizFormPlatform - B端企业入驻管理系统",
  description: "企业表单提交、地理聚合、批处理管理系统",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
            <a href="/" className="font-bold text-lg text-blue-600">BizForm</a>
            <a href="/forms" className="text-sm hover:text-blue-600">表单管理</a>
            <a href="/aggregation" className="text-sm hover:text-blue-600">地理聚合</a>
            <a href="/knowledge" className="text-sm hover:text-blue-600">知识文档</a>
            <a href="/analytics" className="text-sm hover:text-blue-600">数据统计</a>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
