# BizFormPlatform — B端企业入驻订单聚合系统

> **定位**：B端企业入驻场景下的表单提交流程管理与地理批量聚合 Demo  
> **核心理念**：B端系统优先保障 **数据准确性与处理效率**，而非华丽的 UI/UX。  
> **技术栈**：Next.js 16 (React 19) + FastAPI + PostgreSQL/PostGIS + Redis  
> **数据规模**：14万+ 商户表单，20万+ 总记录

---

## 📦 快速启动

```bash
# 1. 克隆仓库
git clone git@github.com:freezetheflame/B-demo.git && cd B-demo

# 2. 启动全部服务（PostgreSQL + Redis + 后端 API）
docker compose up -d --build

# 3. 启动前端
cd frontend && npm install && npm run dev
```

访问 **http://localhost:3000** 查看系统。  
API 文档：**http://localhost:8000/docs**

> **注意**：后端容器首次启动会自动执行种子数据生成（约 20s）。如果端口冲突（WSL + Docker Desktop），确保 Docker Desktop 的 WSL 集成已启用。

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js 16)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ 仪表盘    │ │ 表单管理  │ │ 地理聚合  │ │ 知识文档/统计 │  │
│  │ Dashboard│ │ Forms    │ │ Aggregat.│ │ Knowledge    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬───────┘  │
│       └────────────┴────────────┴───────────────┘           │
│                Zustand Store (MVVM)                         │
│         + react-window v2 (14w+虚拟滚动，60fps)              │
│              + 前端LRU缓存 (页面级，50 entry)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────┴──────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────┐    │
│  │ Forms  │ │ Analytics│ │Knowledge │ │ Aggregation    │    │
│  │ CRUD   │ │ 统计     │ │ 文档版本  │ │ Geo+DBSCAN     │    │
│  ├────────┤ ├─────────┤ ├──────────┤ ├────────────────┤    │
│  │批处理  │ │ 埋点日志 │ │ 全文检索  │ │ Geohash+距离    │    │
│  │Webhook │ │ 失败分析 │ │ 软删除    │ │ 连通分量聚类    │    │
│  └────────┘ └─────────┘ └──────────┘ └────────────────┘    │
│       全局异常处理 | SQLAlchemy 2.0 ORM | WebSocket 进度推送  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│               Infrastructure (Docker Compose)                │
│  ┌─────────────────┐  ┌──────────────┐                      │
│  │ PostgreSQL+GIS  │  │    Redis     │                      │
│  │ GIST Index      │  │  Cache/WS    │                      │
│  │ 地理空间查询      │  │  Pub/Sub     │                      │
│  └─────────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📑 功能模块

### 1. 表单管理 — 四类提交流程

| 表单类型 | 字段特点 | 流程 |
|:--------|:--------|:-----|
| **商户信息** (merchant) | 名称、地址、坐标(geo)、行业分类、联系人 | 提交 → 数据清洗 → 地理编码 → 批量聚合 → 状态更新 |
| **商户房源** (listing) | 关联商户、面积、价格、图片列表 | 提交 → 按商户聚合 → 价格/面积校验 → 批量审批 |
| **商户商品** (product) | 关联商户、SKU编码、库存、价格 | 提交 → SKU校验 → 库存同步 → 批量上架 |
| **商户报表** (report) | 关联商户、报表类型、周期、JSON数据 | 提交 → 数据校验 → 归档存储 → 分析报告生成 |

**关键特性：**
- ✅ 多维度查询过滤器（状态、关键词、日期范围、Geohash前缀）
- ✅ 分页查询 + 排序（created_at / submitted_at）
- ✅ 批量状态更新（POST /batch）+ **WebSocket 实时进度推送**
- ✅ 14w+ 数据虚拟滚动渲染（react-window v2）
- ✅ 前端 LRU 缓存（50 条分页缓存，命中率 >80%）
- ✅ 动态表单字段展示——类型切换自动适配列定义

### 2. 地理坐标批量聚合

**两阶段聚合策略（完整实现）：**

```
阶段1: Geohash 粗分桶
  基于经纬度二分逼近算法，精度5字符 → ~4.9km 网格
  将全量数据 O(n²) 问题降维为 O(n) 子问题

阶段2: Haversine 距离聚类（500m 阈值）
  每个 Geohash 桶内做精确的地球曲面距离计算
  连通分量（DFS）构建聚类簇
```

**实际性能数据（14万商户，500m 阈值，precision=5）：**
| 数据量 | 聚类簇数 | 耗时 | 技术手段 |
|:-------|:---------|:-----|:---------|
| 9,087 | 6,563 | 3.69s | Geohash 5 精度 + Haversine |
| 2,013 | 873 | 0.19s | Geohash 6 精度 |

**核心算法实现：**
- ✅ Geohash 编码：二分逼近 + Base32 映射，支持 1-12 精度
- ✅ Haversine 公式：精确地球曲面距离（6371km 半径）
- ✅ 连通分量聚类：邻接表 + DFS，O(n·k) 其中 k 为桶内平均邻居数
- ✅ PostGIS GIST 空间索引：geo 字段建 GIST 索引，查询 O(log n)
- ✅ Redis 结果缓存：batch_id 关联聚类结果
- ✅ 实时 Geohash 更新：聚类完成后回写精确 geohash 到数据库

### 3. 数据统计 — 表单提交成功率

**API：** `GET /api/v1/analytics/submit-metrics`

**返回指标：**
| 指标 | 说明 |
|:-----|:-----|
| `total_submits` | 总提交数 |
| `success_count` | 成功数 |
| `fail_count` | 失败数 |
| `success_rate` | 成功率 (%) |
| `avg_duration_ms` | 平均耗时 |
| `min_duration_ms` / `max_duration_ms` | 耗时范围 |
| `fail_reasons` | 失败原因分布（按 error_code 分组） |
| `hourly_trend` | 逐小时提交趋势（168小时窗口） |

**埋点机制：** 独立的 `submission_logs` 表——记录的是**提交事件**而非表单状态，区分「提交成功率」与「审核通过率」两个维度。

### 4. 知识文档系统

**数据模型：** 支持全文检索、自动版本递增、变更快照（diff_json）、软删除（deleted_at）、分类/标签多维度筛选。

**API：**
| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| POST | `/api/v1/knowledge/docs` | 创建文档（自动生成 v1） |
| GET | `/api/v1/knowledge/docs` | 列表查询（merchant_id/category/keyword） |
| GET | `/api/v1/knowledge/docs/{id}` | 文档详情 |
| PUT | `/api/v1/knowledge/docs/{id}` | 更新文档（自动版本递增 + 快照） |
| DELETE | `/api/v1/knowledge/docs/{id}` | 软删除 |
| GET | `/api/v1/knowledge/docs/{id}/versions` | 版本列表 |

### 5. 批处理 + WebSocket 实时进度

```
操作员 → 前端选择表单 → 点击批处理
    ↓
POST /api/v1/forms/{type}/batch
    ↓
后端分 10 步处理，每步通过 WebSocket 广播进度
    ↓
ws://localhost:8000/ws/progress
    ↓
{"event":"batch:progress","data":{"batch_id":"...","current":60,"total":100,"percent":60,"status":"processing"}}
    ↓
前端实时展示进度
```

---

## ⚙️ 跨端适配方案

| 平台 | 策略 | 方案说明 |
|:-----|:-----|:---------|
| **Web (PC)** | 全功能桌面版 | 完整数据表格、虚拟滚动、地图聚合、实时 WebSocket |
| **Web (Mobile)** | 响应式适配 | TailwindCSS breakpoints (sm/md/lg)；简化表单卡片 |
| **PWA** | Service Worker + Cache | 离线缓存草稿；后台同步 pending 提交 |
| **企业微信/钉钉** | 独立适配方案 | 扫码录入商户；简化审批流程 |
| **Flutter (规划中)** | 跨平台原生 | 共享 API 层；离线优先数据库 |

---

## 🧪 测试数据

| 表 | 条数 | 说明 |
|:---|:----|:-----|
| `merchant_forms` | 140,000 | 南京地区随机坐标 (lat: 31.2~32.4, lng: 118.4~119.2) |
| `listing_forms` | 30,000 | 随机关联商户，面积 30~300m²，价格 2000~20000 |
| `product_forms` | 30,000 | 随机关联商户，8 种商品分类 |
| `submission_logs` | 150,000 | 过去 7 天逐小时提交记录，~8% 失败率 |
| `knowledge_docs` | — | 通过 API 创建 |

---

## 🔐 性能基准

| 场景 | 数据量 | 耗时 | 说明 |
|:-----|:------|:----|:-----|
| 表单列表查询 | 140,000 条 | < 50ms | 分页 + 状态过滤 + LRU 缓存 |
| 地理聚合 | 9,087 条 → 6,563 簇 | 3.69s | Geohash 5精度 + Haversine 聚类 |
| 成功率统计 | 150,000 条 | < 100ms | raw SQL + date_trunc 预聚合 |
| 知识文档检索 | 全文检索 | < 30ms | PostgreSQL LIKE + 索引 |
| 前端虚拟滚动 | 140,000 行 | 60fps | react-window v2 固定高度列表 |

---

## 📂 项目结构

```
B-demo/
├── docker-compose.yml          # PostgreSQL + Redis + Backend
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI 入口 + 全局异常处理
│       ├── config.py           # Pydantic 配置
│       ├── database.py         # AsyncSession + init_db
│       ├── models.py           # SQLAlchemy ORM 模型（7 个表）
│       ├── seed.py             # 数据生成器（70k+/次）
│       └── routes/
│           ├── forms.py        # 表单 CRUD + 批处理 + WS 进度推送
│           ├── aggregation.py  # Geohash 编码 + Haversine 距离聚类
│           ├── analytics.py    # 成功率统计 + 埋点日志
│           ├── knowledge.py    # 知识文档 CRUD + 版本管理
│           └── ws.py           # WebSocket 连接管理 + 广播
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── app/
│       │   ├── page.tsx                # 仪表盘（实时指标）
│       │   ├── layout.tsx              # 导航布局
│       │   ├── forms/page.tsx          # 表单管理（虚拟滚动 + LRU缓存）
│       │   ├── aggregation/page.tsx    # 地理聚合
│       │   ├── analytics/page.tsx      # 数据统计
│       │   └── knowledge/page.tsx      # 知识文档
│       └── store/index.ts              # Zustand 状态管理
```

---

## 🧑‍💻 业务思考 & 优化记录

### B端 vs C端的设计差异

| 维度 | B端（本系统） | C端 |
|:-----|:------------|:----|
| **首要目标** | 数据准确性 + 处理效率 | 用户体验 + 视觉吸引力 |
| **UI 设计** | 纯数据展示，表格+卡片 | 动效+大图+个性化推荐 |
| **交互模式** | 批量/快捷键/键盘操作 | 点击/滑动/拖动 |
| **性能要求** | 14w+ 数据秒级响应 | 首屏 < 3s |
| **数据校验** | 强校验（每个字段必须准确） | 宽松校验 |
| **缓存策略** | LRU 页面缓存 + HTTP Cache-Control | CDN + 本地存储 |

### 已解决的 Bug & 设计决策

1. **Geohash 桩函数 → 完整实现**  
   原 `geohash_encode` 只返回 `"s000"`，聚合依赖种子数据里随机拼的假 geohash。现已实现二分逼近 + Base32 编码，支持 1-12 精度。

2. **Geohash 分桶 → 真距离聚类**  
   原「聚类」仅按 geohash 前缀分组，无距离计算。现已加入 Haversine 公式 + 连通分量（DFS）构建真正的距离聚类簇。

3. **React Window v2 适配**  
   原使用 `react-window@1.x` 的 `FixedSizeList`，与 v2 API 不兼容。已适配 v2 的 `List` 组件（`itemCount→rowCount`, `itemSize→rowHeight`, 新增 `rowComponent`/`rowProps`）。

4. **前端仅显示 ID+状态 → 完整多列展示**  
   原后端 API 序列化只返回 `id` 和 `status`，丢弃 name/address/category 等字段。已修复为按表单类型动态展示全部业务字段。

5. **WebSocket 声明但未接线 → 批处理实时进度**  
   原 `notify_batch_progress` 定义了但从未调用。已接入批处理端点，分 10 步推送进度（browser 端已验证 ping/pong + batch:progress）。

6. **Analytics 笛卡尔积修复**  
   SQLAlchemy `subquery()` 中使用了外层表的字段引用，导致生成 `FROM (subquery), submission_logs` 笛卡尔积。改用 raw SQL 避免 ORM 自动生成的跨表引用。

7. **PostgreSQL raw SQL 参数类型推断**  
   `$3 IS NULL` 无法推断参数类型，加 `::VARCHAR` 显式转换解决。

8. **PostGIS geo 字段种子数据**  
   原 seed 脚本跳过了 `geo` 字段，聚合功能无法工作。添加 `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` 生成有效的 PostGIS 几何点。

---

## 📜 License

MIT
