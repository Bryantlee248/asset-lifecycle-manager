#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报表统计模块 P2 增量 QA 测试脚本 (S-12 联动下钻 + S-16 阶段趋势 + S-17 时间对比)
作者: Edward (software-qa-engineer)
依赖: requests；后端已在 127.0.0.1:8000 运行（生产模式，新代码已生效）。

覆盖范围:
  A. 登录取 token（字段 token）, 断言 200
  B. 权限边界: 无 Authorization 调 /api/stats/stage-trend 期望 401
  C. stage-trend: 默认 months=12 -> 12 月 / is_backfill=True / 末月 total==100；
                  越界 months=999 被限制（返回值 <=60 或 422 拒绝）；每月 counts 7 阶段齐、Σcounts==total
  D. compare: 环比(2026-06 vs 2026-07) -> "环比"；同比(2025-07 vs 2026-07) -> "同比" 且 a≈92,b=100；
              非法 metric=bad -> 400；自定义(2026-01 vs 2026-07) -> "自定义"
  E. stage 过滤回归: reliability/warranty-buckets/aggregate/category-composition 带 stage=运行 均 200；
      aggregate 带 metric=original_value 时，仅"运行"求和 < 全量（验证过滤真的收窄）
  F. Drawer 复用数据源: GET /api/assets?stage=运行 -> total==49；?category=服务器 -> total>0
  G. 既有 12/12 回归（来自基础模块）: overview/stage-distribution/category-composition(含 category_code)/
      reliability/mtbf(含于 reliability)/warranty-buckets/aggregate 合法+非法/export/多角色 —
      不得因 P2 改动而破坏；重点确认 overview.total_assets==100 / total_original_value==19560662.48 /
      total_faults==33 仍成立
  H. 前端静态校验（读 frontend/index.html）: stage-trend 容器/接口、对比控件/接口、联动下钻 click+状态+清除、
      Drawer 复用 /api/assets、is_backfill 提示文案

用法: python qa-test-report-module-P2.py
"""

import os
import sys
import json
import urllib.parse

try:
    import requests
except ImportError:
    print("[FATAL] requests 未安装，请先 pip install requests")
    sys.exit(2)

BASE = "http://127.0.0.1:8000"

# 账号（4 角色均内置 reports:view 权限）
ACCOUNTS = {
    "admin": "Admin@2026!Secure",
    "test_ops_manager": "Test@2026!",
    "test_ops_engineer": "Test@2026!",
    "test_viewer": "Test@2026!",
}

# 期望值（来自团队/PRD 给定的测试数据基准）
EXP_TOTAL_ASSETS = 100
EXP_TOTAL_ORIGINAL_VALUE = 19560662.48
EXP_TOTAL_FAULTS = 33

# 阶段中文（用于 stage 过滤）
STAGE_RUN = "运行"
CATEGORY_SERVER = "服务器"

# 结果收集
RESULTS = []  # 每项: dict(name, group, passed, detail)


def record(group, name, passed, detail=""):
    RESULTS.append({"group": group, "name": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] ({group}) {name}" + (f"  -- {detail}" if detail else ""))


def login(username):
    """登录并返回 (status_code, json_dict)。注意字段名是 token 而非 access_token。"""
    resp = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": username, "password": ACCOUNTS[username]},
        timeout=15,
    )
    try:
        body = resp.json()
    except Exception:
        body = {}
    return resp.status_code, body


def auth_get(path, token, allow_redirects=False):
    """带 Bearer 的 GET 请求。"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{BASE}{path}", headers=headers, timeout=30,
                        allow_redirects=allow_redirects)


def safe(group, name, fn):
    """执行单个用例，捕获异常并记录。"""
    try:
        fn()
    except AssertionError as e:
        record(group, name, False, f"断言失败: {e}")
    except Exception as e:
        record(group, name, False, f"异常: {type(e).__name__}: {e}")


# ===================== A. 登录 =====================

def test_login_token():
    def _run():
        status, body = login("admin")
        assert status == 200, f"HTTP {status}"
        assert "token" in body, f"响应缺少 token 字段，字段列表: {list(body.keys())}"
        assert isinstance(body.get("token"), str) and body["token"], "token 为空或非字符串"
        assert "token_type" in body, "缺少 token_type"
        assert "user" in body, "缺少 user"
        record("A", "登录获取 token (字段 token / 200 / 非空)", True,
               f"token_type={body.get('token_type')}")
    safe("A", "登录获取 token (字段 token / 200 / 非空)", _run)


# ===================== B. 权限边界 =====================

def test_no_token_401_stage_trend():
    def _run():
        resp = auth_get("/api/stats/stage-trend", token=None)
        assert resp.status_code == 401, f"期望 401，实际 {resp.status_code}"
        record("B", "权限边界: 无 Authorization 调 /api/stats/stage-trend 期望 401", True)
    safe("B", "权限边界: 无 Authorization 调 /api/stats/stage-trend 期望 401", _run)


def test_no_token_401_overview():
    def _run():
        resp = auth_get("/api/stats/overview", token=None)
        assert resp.status_code == 401, f"期望 401，实际 {resp.status_code}"
        record("B", "权限边界(回归): 无 Authorization 调 /api/stats/overview 期望 401", True)
    safe("B", "权限边界(回归): 无 Authorization 调 /api/stats/overview 期望 401", _run)


# ===================== C. stage-trend =====================

def test_stage_trend_default(token):
    def _run():
        resp = auth_get("/api/stats/stage-trend", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        months = d.get("months", [])
        assert len(months) == 12, f"months 长度={len(months)} 期望 12"
        assert d.get("is_backfill") is True, f"is_backfill={d.get('is_backfill')} 期望 True"
        stages = d.get("stages", [])
        assert len(stages) == 7, f"stages 长度={len(stages)} 期望 7"
        matrix = d.get("matrix", [])
        assert matrix, "matrix 为空"
        # 末月 total == 100
        last = matrix[-1]
        assert last.get("total") == EXP_TOTAL_ASSETS, \
            f"末月 total={last.get('total')} 期望 {EXP_TOTAL_ASSETS}"
        # 每月: counts 含 7 阶段且 Σcounts == total
        for m in matrix:
            c = m.get("counts", {})
            assert len(c) == 7, f"month={m.get('month')} counts 阶段数={len(c)} 期望 7"
            assert sum(c.values()) == m.get("total"), \
                f"month={m.get('month')} Σcounts={sum(c.values())} != total={m.get('total')}"
        record("C", "stage-trend 默认 months=12 / is_backfill=True / 末月 total=100 / 每月 7 阶段 & Σcounts==total",
               True, f"末月={last.get('month')} total={last.get('total')}")
    safe("C", "stage-trend 默认 months=12 / is_backfill=True / 末月 total=100", _run)


def test_stage_trend_clamp(token):
    def _run():
        # 越界 months=999：期望被限制（返回值 <=60）或被 422 拒绝。
        # 两种均为"边界受控"的安全行为（满足"应<=60"，不会返回无界数据）。
        resp = auth_get("/api/stats/stage-trend?months=999", token)
        if resp.status_code == 200:
            n = len(resp.json().get("months", []))
            assert n <= 60, f"months 长度={n} 应 <=60"
            detail = f"HTTP 200 夹断至 {n} 月"
        else:
            assert resp.status_code in (400, 422), \
                f"months=999 期望 200(夹断<=60) 或 400/422，实际 {resp.status_code}"
            detail = f"HTTP {resp.status_code}（越界参数被校验拒绝，满足 <=60 边界限制）"
        record("C", "stage-trend 越界 months=999 被限制(<=60 或 422)", True, detail)
    safe("C", "stage-trend 越界 months=999 被限制(<=60 或 422)", _run)


# ===================== D. compare =====================

def test_compare_mom(token):
    def _run():
        resp = auth_get("/api/stats/compare?range_a=2026-06&range_b=2026-07&metric=total_assets", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        assert d.get("compare_type") == "环比", f"compare_type={d.get('compare_type')} 期望 环比"
        record("D", "compare 环比: 2026-06 vs 2026-07 / metric=total_assets -> compare_type=='环比'",
               True, f"a={d['a']['snapshot']} b={d['b']['snapshot']}")
    safe("D", "compare 环比: 2026-06 vs 2026-07 -> compare_type=='环比'", _run)


def test_compare_yoy(token):
    def _run():
        resp = auth_get("/api/stats/compare?range_a=2025-07&range_b=2026-07&metric=total_assets", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        assert d.get("compare_type") == "同比", f"compare_type={d.get('compare_type')} 期望 同比"
        a = d["a"]["snapshot"]
        b = d["b"]["snapshot"]
        assert b == EXP_TOTAL_ASSETS, f"b={b} 期望 {EXP_TOTAL_ASSETS}"
        assert 88 <= a <= 96, f"a={a} 期望≈92（区间 88~96）"
        record("D", "compare 同比: 2025-07 vs 2026-07 -> compare_type=='同比', a≈92, b=100",
               True, f"a={a} b={b} delta={d.get('delta')} delta_pct={d.get('delta_pct')}")
    safe("D", "compare 同比: 2025-07 vs 2026-07 -> compare_type=='同比', a≈92, b=100", _run)


def test_compare_custom(token):
    def _run():
        resp = auth_get("/api/stats/compare?range_a=2026-01&range_b=2026-07&metric=total_assets", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        assert d.get("compare_type") == "自定义", f"compare_type={d.get('compare_type')} 期望 自定义"
        record("D", "compare 自定义: 2026-01 vs 2026-07 -> compare_type=='自定义'",
               True, f"a={d['a']['snapshot']} b={d['b']['snapshot']}")
    safe("D", "compare 自定义: 2026-01 vs 2026-07 -> compare_type=='自定义'", _run)


def test_compare_bad_metric(token):
    def _run():
        resp = auth_get("/api/stats/compare?range_a=2026-06&range_b=2026-07&metric=bad", token)
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
        record("D", "compare 非法 metric=bad -> 400", True)
    safe("D", "compare 非法 metric=bad -> 400", _run)


# ===================== E. stage 过滤回归 + 收窄验证 =====================

def test_stage_filter_regression(token):
    def _run():
        st = urllib.parse.quote(STAGE_RUN)
        cases = {
            "reliability": f"/api/stats/reliability?stage={st}",
            "warranty-buckets": f"/api/stats/warranty-buckets?stage={st}",
            "category-composition": f"/api/stats/category-composition?stage={st}",
            "aggregate": f"/api/stats/aggregate?field=asset_category&metric=original_value&stage={st}",
        }
        for name, path in cases.items():
            r = auth_get(path, token)
            assert r.status_code == 200, f"{name}?stage={STAGE_RUN} HTTP {r.status_code}"
        record("E", "stage 过滤回归: reliability/warranty-buckets/category-composition/aggregate 带 stage=运行 均 200",
               True)
    safe("E", "stage 过滤回归: 4 接口带 stage=运行 均 200", _run)


def test_stage_filter_narrowing(token):
    def _run():
        # 全量 original_value 求和
        r_all = auth_get("/api/stats/aggregate?field=asset_category&metric=original_value", token)
        assert r_all.status_code == 200
        full_sum = sum(float(x.get("original_value", 0)) for x in r_all.json().get("rows", []))
        assert abs(full_sum - EXP_TOTAL_ORIGINAL_VALUE) < 0.01, \
            f"全量 Σoriginal_value={full_sum} 期望≈{EXP_TOTAL_ORIGINAL_VALUE}"

        # 仅"运行"阶段 original_value 求和
        st = urllib.parse.quote(STAGE_RUN)
        r_run = auth_get(f"/api/stats/aggregate?field=asset_category&metric=original_value&stage={st}", token)
        assert r_run.status_code == 200
        run_sum = sum(float(x.get("original_value", 0)) for x in r_run.json().get("rows", []))
        assert run_sum < full_sum, f"仅运行 Σ={run_sum} 未 < 全量 Σ={full_sum}（过滤未收窄）"
        assert abs(run_sum - 9291615) < 1000, f"仅运行 Σ={run_sum} 与参考值 9291615 偏差过大"
        record("E", "stage 过滤收窄验证: 仅运行 original_value 求和 < 全量（≈9291615 < 19560662.48）",
               True, f"全量={full_sum:.2f} 仅运行={run_sum:.2f}")
    safe("E", "stage 过滤收窄验证: 仅运行 original_value 求和 < 全量", _run)


# ===================== F. Drawer 复用数据源 =====================

def test_drawer_stage(token):
    def _run():
        st = urllib.parse.quote(STAGE_RUN)
        r = auth_get(f"/api/assets?stage={st}", token)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        d = r.json()
        assert d.get("total") == 49, f"assets?stage={STAGE_RUN} total={d.get('total')} 期望 49"
        record("F", "Drawer 数据源: GET /api/assets?stage=运行 -> total==49", True,
               f"total={d.get('total')}")
    safe("F", "Drawer 数据源: GET /api/assets?stage=运行 -> total==49", _run)


def test_drawer_category(token):
    def _run():
        cat = urllib.parse.quote(CATEGORY_SERVER)
        r = auth_get(f"/api/assets?category={cat}", token)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        d = r.json()
        assert d.get("total", 0) > 0, f"assets?category={CATEGORY_SERVER} total={d.get('total')} 期望 >0"
        record("F", "Drawer 数据源: GET /api/assets?category=服务器 -> total>0", True,
               f"total={d.get('total')}")
    safe("F", "Drawer 数据源: GET /api/assets?category=服务器 -> total>0", _run)


# ===================== G. 既有 12/12 回归 =====================

def test_overview(token):
    def _run():
        resp = auth_get("/api/stats/overview", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        assert d.get("total_assets") == EXP_TOTAL_ASSETS, \
            f"total_assets={d.get('total_assets')} 期望 {EXP_TOTAL_ASSETS}"
        assert abs(float(d.get("total_original_value", 0)) - EXP_TOTAL_ORIGINAL_VALUE) < 0.01, \
            f"total_original_value={d.get('total_original_value')} 期望 {EXP_TOTAL_ORIGINAL_VALUE}"
        assert d.get("total_faults") == EXP_TOTAL_FAULTS, \
            f"total_faults={d.get('total_faults')} 期望 {EXP_TOTAL_FAULTS}"
        record("G", "overview: total_assets=100 / total_original_value=19560662.48 / total_faults=33", True)
    safe("G", "overview: 100 / 19560662.48 / 33", _run)


def test_stage_distribution(token):
    def _run():
        resp = auth_get("/api/stats/stage-distribution", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        stages = d.get("stages", [])
        assert len(stages) == 7, f"stages 长度={len(stages)} 期望 7"
        sum_count = sum(s.get("count", 0) for s in stages)
        assert sum_count == EXP_TOTAL_ASSETS, f"Σcount={sum_count} 期望 {EXP_TOTAL_ASSETS}"
        sum_ratio = sum(float(s.get("ratio", 0)) for s in stages)
        assert abs(sum_ratio - 1) < 0.001, f"Σratio={sum_ratio} 期望≈1"
        for s in stages:
            assert "stage" in s and "count" in s and "ratio" in s, f"阶段项字段缺失: {s}"
        record("G", "stage-distribution: 长度=7 / Σcount=100 / abs(Σratio-1)<0.001", True)
    safe("G", "stage-distribution: 7 阶段 / Σcount=100", _run)


def test_category_composition(token):
    def _run():
        resp = auth_get("/api/stats/category-composition?include_code=1", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        by_category = d.get("by_category", [])
        assert by_category, "by_category 为空"
        for item in by_category:
            assert "category_code" in item, f"by_category 项缺少 category_code: {item}"
        sum_ov = sum(float(item.get("original_value", 0)) for item in by_category)
        assert abs(sum_ov - EXP_TOTAL_ORIGINAL_VALUE) < 0.01, \
            f"Σby_category.original_value={sum_ov} 期望≈{EXP_TOTAL_ORIGINAL_VALUE}"
        assert d.get("by_model"), "by_model 为空"
        record("G", "category-composition: include_code=1 含 category_code / Σoriginal_value≈19560662.48 / by_model 非空", True)
    safe("G", "category-composition: category_code / Σoriginal_value", _run)


def test_reliability(token):
    def _run():
        resp = auth_get("/api/stats/reliability?top_n=10", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        mtbf = float(d.get("mtbf_days", 0))
        assert mtbf > 0, f"mtbf_days={mtbf} 期望 >0"
        top = d.get("top_fault_assets", [])
        for i in range(len(top) - 1):
            assert top[i]["fault_count"] >= top[i + 1]["fault_count"], "top 未按 fault_count 降序"
        for s in d.get("by_stage_failure_rate", []):
            ac = int(s.get("asset_count", 0))
            fc = int(s.get("fault_count", 0))
            assert "rate" in s, f"by_stage_failure_rate 项缺少 rate: {s}"
            rate = float(s["rate"])
            assert rate >= 0, f"rate 不应为负: {s}"
            if ac > 0:
                exp_rate = round(fc / ac, 4)
                assert abs(rate - exp_rate) < 1e-6, f"rate={rate} 与 fault_count/asset_count={exp_rate} 不一致"
        record("G", "reliability/mtbf: mtbf_days>0 / top 降序 / by_stage rate>=0 且与公式一致", True,
               f"mtbf_days={mtbf}")
    safe("G", "reliability/mtbf: mtbf>0 / rate 公式一致", _run)


def test_warranty_buckets(token):
    def _run():
        resp = auth_get("/api/stats/warranty-buckets", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        buckets = d.get("buckets", {})
        need_keys = {"expired", "within_30", "within_60", "within_90", "over_90"}
        assert need_keys.issubset(buckets.keys()), f"buckets 缺少键: {need_keys - set(buckets.keys())}"
        expiring = d.get("expiring_list", [])
        for i in range(len(expiring) - 1):
            assert expiring[i]["days_left"] <= expiring[i + 1]["days_left"], "expiring_list 未按 days_left 升序"
        for item in expiring:
            assert "asset_code" in item and "days_left" in item, f"清单项缺少 asset_code/days_left: {item}"
        record("G", "warranty-buckets: 五键齐全 / expiring_list 按 days_left 升序", True)
    safe("G", "warranty-buckets: 五键 / 升序", _run)


def test_aggregate_valid(token):
    def _run():
        resp = auth_get("/api/stats/aggregate?field=asset_category&metric=count", token)
        assert resp.status_code == 200, f"count: HTTP {resp.status_code}"
        rows = resp.json().get("rows", [])
        assert rows, "aggregate(count) rows 为空"
        for i in range(len(rows) - 1):
            assert rows[i]["count"] >= rows[i + 1]["count"], "rows 未按 count 降序"
        resp2 = auth_get("/api/stats/aggregate?field=asset_category&metric=original_value", token)
        assert resp2.status_code == 200, f"original_value: HTTP {resp2.status_code}"
        rows2 = resp2.json().get("rows", [])
        assert rows2, "aggregate(original_value) rows 为空"
        for r in rows2:
            assert "original_value" in r, f"row 缺少 original_value: {r}"
        sum_ov = sum(float(r.get("original_value", 0)) for r in rows2)
        assert abs(sum_ov - EXP_TOTAL_ORIGINAL_VALUE) < 0.01, f"Σoriginal_value={sum_ov} 期望≈{EXP_TOTAL_ORIGINAL_VALUE}"
        record("G", "aggregate 合法: count 降序非空 / original_value Σ≈19560662.48", True)
    safe("G", "aggregate 合法: count/original_value", _run)


def test_aggregate_invalid(token):
    def _run():
        resp = auth_get("/api/stats/aggregate?field=invalid_xyz&metric=count", token)
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
        # 缺 field 也应 400
        resp2 = auth_get("/api/stats/aggregate?metric=count", token)
        assert resp2.status_code == 400, f"缺 field 期望 400，实际 {resp2.status_code}"
        record("G", "aggregate 非法: field=invalid_xyz -> 400；缺 field -> 400", True)
    safe("G", "aggregate 非法: 400", _run)


def test_export(token):
    def _run():
        resp = auth_get("/api/stats/export", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        ct = resp.headers.get("Content-Type", "")
        disp = resp.headers.get("Content-Disposition", "")
        ok = ("spreadsheet" in ct) or disp.lower().endswith(".xlsx") or (".xlsx" in disp) \
            or (resp.content[:4] == b"PK\x03\x04")
        assert ok, f"Content-Type={ct} 且未识别为 xlsx (disp={disp})"
        assert len(resp.content) > 0, "导出内容为空"
        record("G", "export: GET /api/stats/export 返回 200 且为 spreadsheet/.xlsx", True, f"Content-Type={ct}")
    safe("G", "export: xlsx", _run)


def test_multi_role(role):
    def _run():
        status, body = login(role)
        assert status == 200, f"{role} 登录失败 HTTP {status}"
        tok = body.get("token")
        assert tok, f"{role} token 为空"
        resp = auth_get("/api/stats/overview", tok)
        assert resp.status_code == 200, f"{role} 调 overview 期望 200，实际 {resp.status_code}"
        record("G", f"多角色授权: {role} 调 /api/stats/overview 返回 200", True)
    safe("G", f"多角色授权: {role}", _run)


# ===================== H. 前端静态校验 =====================

def frontend_static_checks():
    """读 frontend/index.html，静态确认 P2 关键元素存在（自动化无法渲染 ECharts）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    idx = os.path.normpath(os.path.join(here, "..", "frontend", "index.html"))
    if not os.path.exists(idx):
        record("H", "前端静态校验: 找不到 frontend/index.html", False, f"路径={idx}")
        return
    with open(idx, "r", encoding="utf-8") as f:
        html = f.read()

    def has(label, *needles):
        missing = [n for n in needles if n not in html]
        if missing:
            record("H", label, False, f"缺失: {missing}")
        else:
            record("H", label, True, "存在")

    # 1) stage-trend 图表容器 + 调 /api/stats/stage-trend
    has("前端: stage-trend 容器 + 调 /api/stats/stage-trend",
        "chart-stage-trend", "/api/stats/stage-trend")
    # 2) 对比控件（环比/同比 + 选月 + metric 选择）+ 调 /api/stats/compare
    has("前端: 对比控件(环比/同比按钮 + 选月 + metric) + 调 /api/stats/compare",
        "环比", "同比", "/api/stats/compare", "compareMetric")
    # 3) chart-stage / chart-category click 监听 + selectedStage/selectedCategory + 清除筛选
    has("前端: chart-stage/chart-category 联动下钻(click + selectedStage/selectedCategory + 清除筛选)",
        "chart-stage", "chart-category", "selectedStage", "selectedCategory",
        "clearFilter", "清除筛选")
    # 4) 明细 Drawer 复用 /api/assets?stage= / ?category=
    has("前端: 明细 Drawer 复用 GET /api/assets?stage= / ?category=",
        "api('/api/assets", "stage", "category", "openDrawer")
    # 5) is_backfill 提示文案（回填口径标注）
    has("前端: is_backfill 提示文案（回填口径标注）",
        "isBackfill", "回填")


# ===================== 主流程 =====================

def main():
    print("=" * 70)
    print("报表统计模块 P2 增量 QA 测试 (Edward)")
    print(f"后端: {BASE}")
    print("=" * 70)

    # A. 登录
    test_login_token()

    _, admin_body = login("admin")
    admin_token = admin_body.get("token")
    if not admin_token:
        record("A", "准备 admin token 失败，后续依赖 token 的用例跳过", False)
        print("\n无法获取 admin token，终止。")
        return _summarize()

    # B. 权限边界
    test_no_token_401_stage_trend()
    test_no_token_401_overview()

    # C. stage-trend
    test_stage_trend_default(admin_token)
    test_stage_trend_clamp(admin_token)

    # D. compare
    test_compare_mom(admin_token)
    test_compare_yoy(admin_token)
    test_compare_custom(admin_token)
    test_compare_bad_metric(admin_token)

    # E. stage 过滤回归 + 收窄
    test_stage_filter_regression(admin_token)
    test_stage_filter_narrowing(admin_token)

    # F. Drawer 数据源
    test_drawer_stage(admin_token)
    test_drawer_category(admin_token)

    # G. 既有 12/12 回归
    test_overview(admin_token)
    test_stage_distribution(admin_token)
    test_category_composition(admin_token)
    test_reliability(admin_token)
    test_warranty_buckets(admin_token)
    test_aggregate_valid(admin_token)
    test_aggregate_invalid(admin_token)
    test_export(admin_token)
    test_multi_role("test_ops_manager")
    test_multi_role("test_viewer")

    # H. 前端静态校验
    frontend_static_checks()

    return _summarize()


def _summarize():
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed
    rate = (passed / total * 100) if total else 0

    # 按组统计
    groups = {}
    for r in RESULTS:
        g = r["group"]
        groups.setdefault(g, {"total": 0, "passed": 0})
        groups[g]["total"] += 1
        groups[g]["passed"] += 1 if r["passed"] else 0

    print("\n" + "=" * 70)
    print(f"测试汇总: 总计 {total} | 通过 {passed} | 失败 {failed} | 通过率 {rate:.1f}%")
    print("-" * 70)
    for g in sorted(groups):
        gs = groups[g]
        print(f"  组 {g}: {gs['passed']}/{gs['total']}")
    print("=" * 70)

    if failed == 0:
        routing = "NoOne"
    else:
        routing = "待判定(需结合失败用例区分源码 Bug / 测试代码 Bug)"

    print(f"智能路由判定: {routing}")

    print("\n#RESULT_JSON#" + json.dumps({
        "total": total, "passed": passed, "failed": failed,
        "rate": round(rate, 1), "routing": routing, "cases": RESULTS
    }, ensure_ascii=False))

    return {"total": total, "passed": passed, "failed": failed, "rate": rate, "routing": routing}


if __name__ == "__main__":
    summary = main()
    if summary and summary["failed"] > 0:
        sys.exit(1)
    sys.exit(0)
