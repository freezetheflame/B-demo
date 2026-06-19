"""
Integration tests against the running backend API.

Run with:  pytest tests/test_api.py -v

Tests:
  - test_list_forms_has_full_fields    → API 返回完整字段
  - test_aggregation_run               → POST /run 聚类
  - test_batch_with_websocket          → 批处理 + WS 握手
"""

import pytest
import socket
import httpx


# ═══════════════════════════════════════════════════════════════
# 功能点 4: 表单列表 API — 全字段返回
# 验证后端序列化修复后返回 name/address/category 等字段
# ═══════════════════════════════════════════════════════════════

def test_list_merchant_forms_has_full_fields(client: httpx.Client):
    """商户表单列表应包含 name + address + category + contact_name + status。"""
    resp = client.get("/api/v1/forms/merchant?page=1&page_size=5")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] > 1000, "种子数据应 > 1000 条商户"

    rows = data["data"]
    assert len(rows) > 0

    first = rows[0]
    assert "name" in first, "应返回商户名称"
    assert "address" in first, "应返回地址"
    assert "category" in first, "应返回行业分类"
    assert "contact_name" in first, "应返回联系人"
    assert "status" in first
    assert first["name"], "商户名称不应为空"


def test_list_listing_forms_shows_correct_columns(client: httpx.Client):
    """房源表单应包含 title + area + price。"""
    resp = client.get("/api/v1/forms/listing?page=1&page_size=3")
    assert resp.status_code == 200
    first = resp.json()["data"][0]
    assert "title" in first
    assert "area" in first
    assert "price" in first


def test_list_product_forms_shows_sku_and_stock(client: httpx.Client):
    """商品表单应包含 sku + price + stock。"""
    resp = client.get("/api/v1/forms/product?page=1&page_size=3")
    assert resp.status_code == 200
    first = resp.json()["data"][0]
    assert "sku" in first
    assert "stock" in first
    assert "price" in first


def test_forms_page_respects_pagination(client: httpx.Client):
    """分页：page=1 和 page=2 不应返回相同记录。"""
    p1 = client.get("/api/v1/forms/merchant?page=1&page_size=3")
    p2 = client.get("/api/v1/forms/merchant?page=2&page_size=3")
    ids1 = {r["id"] for r in p1.json()["data"]}
    ids2 = {r["id"] for r in p2.json()["data"]}
    assert ids1.isdisjoint(ids2), "两页数据不应重复"


def test_forms_filter_by_status(client: httpx.Client):
    """按状态过滤应返回正确状态。"""
    resp = client.get("/api/v1/forms/merchant?status=submitted&page_size=5")
    assert resp.status_code == 200
    for row in resp.json()["data"]:
        assert row["status"] in ("submitted", "SUBMITTED"), f"Got {row['status']}"


# ═══════════════════════════════════════════════════════════════
# 功能点 5: 地理聚合 API
# ═══════════════════════════════════════════════════════════════

def test_health_endpoint(client: httpx.Client):
    """健康检查端点可用。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_aggregation_run_returns_correct_schema(client: httpx.Client):
    """聚合端点返回正确的响应结构。"""
    resp = client.post("/api/v1/aggregation/run?distance_m=500&precision=5")
    assert resp.status_code == 200

    result = resp.json()
    assert result["status"] == "ok"
    assert "total_forms" in result
    assert "clusters" in result
    assert "elapsed_seconds" in result
    assert result["distance_m"] == 500
    assert result["elapsed_seconds"] < 30, f"耗时过长: {result['elapsed_seconds']}s"


def test_aggregation_clusters_lte_forms(client: httpx.Client):
    """簇数 ≤ 表单数。"""
    resp = client.post("/api/v1/aggregation/run?distance_m=500&precision=5")
    result = resp.json()
    assert result["clusters"] <= result["total_forms"]


# ═══════════════════════════════════════════════════════════════
# 功能点 6: 批处理 + WebSocket
# ═══════════════════════════════════════════════════════════════

def test_batch_process_updates_status(client: httpx.Client):
    """批处理更新选中表单状态为 processing。"""
    resp = client.get("/api/v1/forms/merchant?status=submitted&page_size=5")
    ids = [r["id"] for r in resp.json()["data"]]
    if not ids:
        pytest.skip("No submitted forms available")

    resp = client.post("/api/v1/forms/merchant/batch", json=ids)
    assert resp.status_code == 200
    assert resp.json()["updated"] == len(ids)


def test_websocket_endpoint_accepts_connection():
    """WebSocket 端点返回 101 Switching Protocols。"""
    s = socket.create_connection(("localhost", 8000), timeout=3)
    s.sendall(
        b"GET /ws/progress HTTP/1.1\r\n"
        b"Host: localhost:8000\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"\r\n"
    )
    resp = s.recv(4096).decode()
    s.close()
    assert "101" in resp, f"Expected 101, got: {resp[:100]}"
