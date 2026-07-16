#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报表统计模块 QA 测试脚本
作者: Edward (software-qa-engineer)
目标: 对 /api/stats/* 七个接口做全面回归验证，覆盖：
      - 鉴权边界（无 token -> 401）
      - KPI 概览 / 阶段分布 / 分类构成 / 可靠性 / 维保分桶 / 自定义聚合 / Excel 导出
      - 多角色 reports:view 授权一致性
      - 非法聚合参数 -> 400
依赖: requests（已确认可用）；后端已在 127.0.0.1:8000 运行。
用法: python qa-test-report-module.py
"""

import sys
import json

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

# 结果收集
RESULTS = []  # 每项: dict(name, passed, detail)


def record(name, passed, detail=""):
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail else ""))


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


def safe(label, fn):
    """执行单个用例，捕获异常并记录。"""
    try:
        fn()
    except AssertionError as e:
        record(label, False, f"断言失败: {e}")
    except Exception as e:
        record(label, False, f"异常: {type(e).__name__}: {e}")


# ===================== 用例实现 =====================

def test_login_token():
    def _run():
        status, body = login("admin")
        assert status == 200, f"HTTP {status}"
        assert "token" in body, f"响应缺少 token 字段，字段列表: {list(body.keys())}"
        assert isinstance(body.get("token"), str) and body["token"], "token 为空或非字符串"
        assert "token_type" in body, "缺少 token_type"
        assert "user" in body, "缺少 user"
        record("登录获取 token (字段 token / 200 / 非空)", True,
               f"token_type={body.get('token_type')}")
    safe("登录获取 token (字段 token / 200 / 非空)", _run)


def test_no_token_401():
    def _run():
        resp = auth_get("/api/stats/overview", token=None)
        assert resp.status_code == 401, f"期望 401，实际 {resp.status_code}"
        record("权限边界: 无 Authorization 调 overview 期望 401", True)
    safe("权限边界: 无 Authorization 调 overview 期望 401", _run)


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
        record("overview: total_assets=100 / total_original_value=19560662.48 / total_faults=33",
               True)
    safe("overview: total_assets=100 / total_original_value=19560662.48 / total_faults=33", _run)


def test_stage_distribution(token):
    def _run():
        resp = auth_get("/api/stats/stage-distribution", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        stages = d.get("stages", [])
        assert len(stages) == 7, f"stages 长度={len(stages)} 期望 7（7 阶段全覆盖）"
        sum_count = sum(s.get("count", 0) for s in stages)
        assert sum_count == EXP_TOTAL_ASSETS, f"Σcount={sum_count} 期望 {EXP_TOTAL_ASSETS}"
        sum_ratio = sum(float(s.get("ratio", 0)) for s in stages)
        assert abs(sum_ratio - 1) < 0.001, f"Σratio={sum_ratio} 期望≈1 (误差<0.001)"
        # 校验每项字段完整
        for s in stages:
            assert "stage" in s and "count" in s and "ratio" in s, f"阶段项字段缺失: {s}"
        record("stage-distribution: 长度=7 / Σcount=100 / abs(Σratio-1)<0.001", True)
    safe("stage-distribution: 长度=7 / Σcount=100 / abs(Σratio-1)<0.001", _run)


def test_category_composition(token):
    def _run():
        resp = auth_get("/api/stats/category-composition?include_code=1", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        by_category = d.get("by_category", [])
        assert by_category, "by_category 为空"
        # include_code=1 时每项应含 category_code
        for item in by_category:
            assert "category_code" in item, f"by_category 项缺少 category_code: {item}"
        sum_ov = sum(float(item.get("original_value", 0)) for item in by_category)
        assert abs(sum_ov - EXP_TOTAL_ORIGINAL_VALUE) < 0.01, \
            f"Σby_category.original_value={sum_ov} 期望≈{EXP_TOTAL_ORIGINAL_VALUE}"
        by_model = d.get("by_model", [])
        assert by_model, "by_model 为空（期望非空）"
        record("category-composition: include_code=1 含 category_code / Σoriginal_value≈19560662.48 / by_model 非空",
               True)
    safe("category-composition: include_code=1 含 category_code / Σoriginal_value≈19560662.48 / by_model 非空", _run)


def test_reliability(token):
    def _run():
        resp = auth_get("/api/stats/reliability?top_n=10", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        mtbf = float(d.get("mtbf_days", 0))
        assert mtbf > 0, f"mtbf_days={mtbf} 期望 >0"
        top = d.get("top_fault_assets", [])
        for i in range(len(top) - 1):
            assert top[i]["fault_count"] >= top[i + 1]["fault_count"], \
                f"top_fault_assets 未按 fault_count 降序: {top[i]} vs {top[i+1]}"
        # 按设计文档(§3.3)定义: rate = fault_count / asset_count，可超过 1
        # （同一资产可有多条故障，故"每资产故障数"可能 >1，非概率）。
        # 校验: rate>=0 且与公式一致、字段齐全。
        for s in d.get("by_stage_failure_rate", []):
            ac = int(s.get("asset_count", 0))
            fc = int(s.get("fault_count", 0))
            assert "rate" in s, f"by_stage_failure_rate 项缺少 rate: {s}"
            rate = float(s["rate"])
            assert rate >= 0, f"rate 不应为负: {s}"
            if ac > 0:
                exp_rate = round(fc / ac, 4)
                assert abs(rate - exp_rate) < 1e-6, \
                    f"rate={rate} 与公式 fault_count/asset_count={exp_rate} 不一致: {s}"
        record("reliability: mtbf_days>0 / top 降序 / by_stage rate>=0 且与 fault_count/asset_count 一致",
               True)
    safe("reliability: mtbf_days>0 / top 降序 / by_stage rate∈[0,1]", _run)


def test_warranty_buckets(token):
    def _run():
        resp = auth_get("/api/stats/warranty-buckets", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        buckets = d.get("buckets", {})
        need_keys = {"expired", "within_30", "within_60", "within_90", "over_90"}
        assert need_keys.issubset(buckets.keys()), \
            f"buckets 缺少键: {need_keys - set(buckets.keys())}"
        expiring = d.get("expiring_list", [])
        # 按 days_left 升序
        for i in range(len(expiring) - 1):
            assert expiring[i]["days_left"] <= expiring[i + 1]["days_left"], \
                f"expiring_list 未按 days_left 升序: {expiring[i]} vs {expiring[i+1]}"
        for item in expiring:
            assert "asset_code" in item and "days_left" in item, \
                f"清单项缺少 asset_code/days_left: {item}"
        record("warranty-buckets: 五键齐全 / expiring_list 按 days_left 升序 / 含 asset_code,days_left",
               True)
    safe("warranty-buckets: 五键齐全 / expiring_list 按 days_left 升序 / 含 asset_code,days_left", _run)


def test_aggregate_valid(token):
    def _run():
        # metric=count
        resp = auth_get("/api/stats/aggregate?field=asset_category&metric=count", token)
        assert resp.status_code == 200, f"count: HTTP {resp.status_code}"
        d = resp.json()
        rows = d.get("rows", [])
        assert rows, "aggregate(count) rows 为空（期望非空）"
        for i in range(len(rows) - 1):
            assert rows[i]["count"] >= rows[i + 1]["count"], \
                f"rows 未按 count 降序: {rows[i]} vs {rows[i+1]}"
        # metric=original_value
        resp2 = auth_get("/api/stats/aggregate?field=asset_category&metric=original_value", token)
        assert resp2.status_code == 200, f"original_value: HTTP {resp2.status_code}"
        d2 = resp2.json()
        rows2 = d2.get("rows", [])
        assert rows2, "aggregate(original_value) rows 为空"
        for r in rows2:
            assert "original_value" in r, f"row 缺少 original_value: {r}"
        sum_ov = sum(float(r.get("original_value", 0)) for r in rows2)
        assert abs(sum_ov - EXP_TOTAL_ORIGINAL_VALUE) < 0.01, \
            f"Σoriginal_value={sum_ov} 期望≈{EXP_TOTAL_ORIGINAL_VALUE}"
        record("aggregate 合法: count 降序非空 / original_value 含 original_value 且 Σ≈19560662.48",
               True)
    safe("aggregate 合法: count 降序非空 / original_value 含 original_value 且 Σ≈19560662.48", _run)


def test_aggregate_invalid(token):
    def _run():
        resp = auth_get("/api/stats/aggregate?field=invalid_xyz&metric=count", token)
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
        record("aggregate 非法: field=invalid_xyz 返回 400", True)
    safe("aggregate 非法: field=invalid_xyz 返回 400", _run)


def test_export(token):
    def _run():
        resp = auth_get("/api/stats/export", token)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        ct = resp.headers.get("Content-Type", "")
        disp = resp.headers.get("Content-Disposition", "")
        ok = ("spreadsheet" in ct) or disp.lower().endswith(".xlsx") or \
             (".xlsx" in disp) or (resp.content[:4] == b"PK\x03\x04")
        assert ok, f"Content-Type={ct} 且未识别为 xlsx (disp={disp})"
        assert len(resp.content) > 0, "导出内容为空"
        record("export: GET /api/stats/export 返回 200 且为 spreadsheet/.xlsx 有效文件", True,
               f"Content-Type={ct}")
    safe("export: GET /api/stats/export 返回 200 且为 spreadsheet/.xlsx 有效文件", _run)


def test_multi_role(role):
    def _run():
        status, body = login(role)
        assert status == 200, f"{role} 登录失败 HTTP {status}"
        tok = body.get("token")
        assert tok, f"{role} token 为空"
        resp = auth_get("/api/stats/overview", tok)
        assert resp.status_code == 200, \
            f"{role} 调 overview 期望 200，实际 {resp.status_code}"
        record(f"多角色授权: {role} 调 /api/stats/overview 返回 200", True)
    safe(f"多角色授权: {role} 调 /api/stats/overview 返回 200", _run)


# ===================== 主流程 =====================

def main():
    print("=" * 70)
    print("报表统计模块 QA 测试 (Edward)")
    print(f"后端: {BASE}")
    print("=" * 70)

    # 1) 登录
    test_login_token()

    # 获取 admin token 供后续用例复用
    _, admin_body = login("admin")
    admin_token = admin_body.get("token")
    if not admin_token:
        record("准备 admin token 失败，后续依赖 token 的用例跳过", False)
        print("\n无法获取 admin token，终止。请检查后端登录接口。")
        return

    # 2) 权限边界
    test_no_token_401()

    # 3) 各接口业务断言
    test_overview(admin_token)
    test_stage_distribution(admin_token)
    test_category_composition(admin_token)
    test_reliability(admin_token)
    test_warranty_buckets(admin_token)
    test_aggregate_valid(admin_token)
    test_aggregate_invalid(admin_token)
    test_export(admin_token)

    # 4) 多角色授权一致
    test_multi_role("test_ops_manager")
    test_multi_role("test_viewer")

    # 汇总
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed
    rate = (passed / total * 100) if total else 0
    print("\n" + "=" * 70)
    print(f"测试汇总: 总计 {total} | 通过 {passed} | 失败 {failed} | 通过率 {rate:.1f}%")
    print("=" * 70)

    # 输出结构化结果（供报告引用）
    print("\n#RESULT_JSON#" + json.dumps({
        "total": total, "passed": passed, "failed": failed,
        "rate": round(rate, 1), "cases": RESULTS
    }, ensure_ascii=False))

    return {"total": total, "passed": passed, "failed": failed, "rate": rate}


if __name__ == "__main__":
    summary = main()
    if summary and summary["failed"] > 0:
        sys.exit(1)
    sys.exit(0)
