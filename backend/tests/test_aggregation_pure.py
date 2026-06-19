"""
Pure unit tests for aggregation module — no database required.

Tests:
  - test_geohash_encode    → Geohash 编码正确性、精度、幂等性
  - test_haversine_m       → Haversine 距离计算、边界条件
  - test_cluster_by_distance → 连通分量聚类逻辑
"""

import pytest
from app.routes.aggregation import geohash_encode, haversine_m, cluster_by_distance


# ═══════════════════════════════════════════════════════════════
# 功能点 1: Geohash 编码
# 测试编码算法的正确性 — 这是聚合系统的基石
# ═══════════════════════════════════════════════════════════════

class TestGeohashEncode:
    """验证 Geohash 编码算法的四个关键属性。"""

    def test_precision_controls_output_length(self):
        """精度参数直接控制输出字符串长度。"""
        assert len(geohash_encode(32.04, 118.78, precision=5)) == 5
        assert len(geohash_encode(32.04, 118.78, precision=7)) == 7
        assert len(geohash_encode(32.04, 118.78, precision=12)) == 12

    def test_deterministic_same_coordinates_same_hash(self):
        """相同坐标 + 相同精度 → 相同 geohash（幂等性）。"""
        h1 = geohash_encode(31.5, 118.5, precision=6)
        h2 = geohash_encode(31.5, 118.5, precision=6)
        assert h1 == h2

    def test_nearby_points_share_prefix(self):
        """相邻坐标共享 geohash 前缀——这是粗分桶成立的前提。"""
        # 南京新街口附近两个非常近的点
        h1 = geohash_encode(32.040, 118.780, precision=7)
        h2 = geohash_encode(32.041, 118.781, precision=7)
        # 相距 ~150m 的两个点应有相同的前 5 个字符
        assert h1[:5] == h2[:5]

    def test_far_apart_points_different_hash(self):
        """远距离坐标 geohash 前缀不同——分桶才能生效。"""
        h_nanjing = geohash_encode(32.04, 118.78, precision=5)
        h_beijing = geohash_encode(39.90, 116.40, precision=5)
        assert h_nanjing != h_beijing

    def test_base32_characters_only(self):
        """编码结果只包含 Base32 字符集（非标准 base32，geohash 专用）。"""
        BASE32 = set("0123456789bcdefghjkmnpqrstuvwxyz")
        h = geohash_encode(32.04, 118.78, precision=12)
        assert set(h).issubset(BASE32)

    def test_extreme_coordinates_dont_crash(self):
        """极端坐标（极点、国际日期变更线）不崩溃。"""
        # 北极点
        result = geohash_encode(89.9, 0, precision=6)
        assert len(result) == 6
        # 日期变更线
        result = geohash_encode(0, 179.9, precision=6)
        assert len(result) == 6


# ═══════════════════════════════════════════════════════════════
# 功能点 2: Haversine 距离计算
# 测试地球曲面距离公式 — 聚类精度依赖准确的度量
# ═══════════════════════════════════════════════════════════════

class TestHaversine:
    """验证 Haversine 公式的关键行为。"""

    def test_zero_distance_same_point(self):
        """同一点距离为 0。"""
        dist = haversine_m(32.0, 118.5, 32.0, 118.5)
        assert dist == 0.0

    def test_known_distance_reference(self):
        """用已知距离验证——南京新街口到鼓楼 ~2.5km。"""
        # 新街口 (32.041, 118.784) → 鼓楼 (32.060, 118.781)
        dist = haversine_m(32.041, 118.784, 32.060, 118.781)
        # 预期约 2.1 km，允许 ±5% 误差
        assert 1900 < dist < 2300, f"Expected ~2100m, got {dist:.0f}m"

    def test_equator_distance_approximately_correct(self):
        """赤道上 1 度经度 ≈ 111 km。"""
        dist = haversine_m(0, 0, 0, 1.0)
        assert 110_000 < dist < 112_000, f"Expected ~111km, got {dist:.0f}m"

    def test_short_distance_within_threshold(self):
        """短距离测试——500m 阈值聚类可靠性的基础。"""
        # 相距约 100m 的两点
        dist = haversine_m(32.040, 118.780, 32.041, 118.780)
        assert 80 < dist < 150, f"Expected ~100m, got {dist:.0f}m"

    def test_distance_is_symmetric(self):
        """Haversine 满足对称性：d(A,B) = d(B,A)。"""
        d1 = haversine_m(32.04, 118.78, 39.90, 116.40)
        d2 = haversine_m(39.90, 116.40, 32.04, 118.78)
        assert abs(d1 - d2) < 0.01  # 浮点误差容忍


# ═══════════════════════════════════════════════════════════════
# 功能点 3: 连通分量聚类
# 测试基于距离阈值的聚类——聚合系统的最后一步
# ═══════════════════════════════════════════════════════════════

class TestClusterByDistance:
    """验证连通分量（DFS）聚类的正确性。"""

    def test_single_point_forms_one_cluster(self):
        """单点自成簇。"""
        pts = [(1, 32.0, 118.5)]
        clusters = cluster_by_distance(pts, 500)
        assert len(clusters) == 1
        assert len(clusters["cluster_0"]) == 1

    def test_close_points_merge_into_same_cluster(self):
        """500m 内的两点归入同一簇。"""
        pts = [
            (1, 32.040, 118.780),
            (2, 32.041, 118.781),  # ~150m away
        ]
        clusters = cluster_by_distance(pts, 500)
        assert len(clusters) == 1
        ids = [p[0] for p in list(clusters.values())[0]]
        assert set(ids) == {1, 2}

    def test_far_points_form_separate_clusters(self):
        """距离超过阈值的两点分别成簇。"""
        pts = [
            (1, 32.04, 118.78),  # 南京
            (2, 39.90, 116.40),  # 北京
        ]
        clusters = cluster_by_distance(pts, 500)
        assert len(clusters) == 2

    def test_three_points_chain_clusters_correctly(self):
        """链式连接: A—B (300m) + B—C (300m) = A,B,C 同一簇（即使 A—C 可能 > 500m）。"""
        # 构造链：三个点在一条线上，相邻间距 300m
        # lat 每 0.0027° ≈ 300m
        pts = [
            (1, 32.000, 118.500),
            (2, 32.0027, 118.500),  # ~300m from pt1
            (3, 32.0054, 118.500),  # ~300m from pt2, ~600m from pt1
        ]
        clusters = cluster_by_distance(pts, 500)
        # A—B < 500, B—C < 500, 但因为连通分量，A—C 也被合并
        assert len(clusters) == 1
        ids = [p[0] for p in list(clusters.values())[0]]
        assert set(ids) == {1, 2, 3}

    def test_empty_input_returns_empty(self):
        """空列表返回空字典。"""
        assert cluster_by_distance([], 500) == {}

    def test_clusters_are_disjoint(self):
        """每条记录只出现在一个簇中。"""
        pts = [(i, 32.0 + i * 0.001, 118.5 + i * 0.001) for i in range(20)]
        clusters = cluster_by_distance(pts, 300)
        all_ids = []
        for cluster_pts in clusters.values():
            all_ids.extend(p[0] for p in cluster_pts)
        assert len(all_ids) == len(set(all_ids)) == 20  # 无重复
