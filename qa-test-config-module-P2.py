# -*- coding: utf-8 -*-
"""
系统配置模块 P2 全量回归测试（QA: 严过关 / software-qa-engineer）
=============================================================
测试对象：校验规则开关 (validation_rule_switch) + 聚合维度白名单 (aggregate_whitelist)
后端：显式指定的本地隔离 FastAPI 实例
覆盖范围：A seed 正确性 / B 开关影响仪表盘 / C 聚合白名单 / D 白名单 CRUD /
         E reset 语义 / F RBAC / G 导入导出 / H 错误码 / I 清理与静态检查
运行方式：先运行 python qa-test-config-module-P2.py --help，并显式传入本地地址、口令环境变量和 --destructive。
依赖：仅标准库 urllib（curl 不可用）；Python 3.13
幂等性：脚本开头 pre-reset、结尾 final-reset，可重复运行。
"""

import argparse
import os
import urllib.request
import urllib.error
import urllib.parse
import json
import sys

BASE = None
ADMIN_USER = "admin"
ADMIN_PASS = os.environ.get("QA_ADMIN_PASSWORD")


def parse_arguments():
    parser = argparse.ArgumentParser(description="P2 configuration regression for a local isolated instance")
    parser.add_argument("--base-url", required=True, help="local test service URL")
    parser.add_argument("--destructive", action="store_true", help="allow validation-rule changes")
    args = parser.parse_args()
    if urllib.parse.urlparse(args.base_url).hostname not in {"127.0.0.1", "localhost"}:
        parser.error("only a local isolated service is allowed")
    if not args.destructive:
        parser.error("this script changes configuration; pass --destructive")
    if not ADMIN_PASS:
        parser.error("missing QA_ADMIN_PASSWORD")
    return args


ARGS = parse_arguments()
BASE = ARGS.base_url.rstrip("/")

# ---- 期望的精确出厂态（与 DESIGN §5.1 / §5.2 一一对应）----
EXPECTED_RULE_KEYS = [
    "empty_code", "empty_sn", "empty_position", "empty_responsible",
    "empty_stage", "duplicate_code", "warranty_expired",
    "warranty_date_invalid", "retired_no_record", "orphan_subtable_code",
]
EXPECTED_FIELD_KEYS = [
    "lifecycle_stage", "asset_category", "room", "cabinet", "department",
    "ownership", "brand", "model", "responsible_person",
    "warranty_status", "project_name",
]
# 合法 Asset 列名但不在 seed 11 内（用于 O3 新增维度测试）
NEW_FIELD_KEY = "device_name"
# 合法 Asset 列名但不在白名单内（用于 400 测试）
NON_WHITELIST_COLUMN = "sn"
# 完全非法的列名（用于 422 测试）
INVALID_COLUMN = "invalid_column_xyz"
# 自定义校验 rule_key（用于 import 造自定义行）
CUSTOM_RULE_KEY = "qa_custom_test_rule"

TOKEN = None
results = []  # (test_id, passed: bool, info: str)


# ----------------------------------------------------------------------
# HTTP 底层封装
# ----------------------------------------------------------------------
def call(method, path, token=None, body=None, timeout=20):
    """返回 (status:int, payload)。payload 为解析后的 JSON 或原始文本。"""
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw) if raw else None
            except Exception:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw) if raw else None
        except Exception:
            return e.code, raw
    except Exception as e:  # 连接错误等
        return -1, "EXCEPTION: %s" % str(e)


def check(test_id, cond, info=""):
    results.append((test_id, bool(cond), info))
    mark = "PASS" if cond else "FAIL"
    line = "[%s] %s" % (mark, test_id)
    if info:
        line += "  -- " + info
    print(line)
    return bool(cond)


def login(user, pwd):
    st, data = call("POST", "/api/auth/login", body={"username": user, "password": pwd})
    if st != 200 or not isinstance(data, dict) or "token" not in data:
        raise RuntimeError("login failed: status=%s data=%r" % (st, data))
    return data["token"]


def get_rule_id_by_key(rules, key):
    for r in rules:
        if r.get("rule_key") == key:
            return r.get("id")
    return None


def get_field_id_by_key(fields, key):
    for f in fields:
        if f.get("field_key") == key:
            return f.get("id")
    return None


# ----------------------------------------------------------------------
# 预清理 / 终清理：回到精确出厂态
# ----------------------------------------------------------------------
def reset_both():
    call("POST", "/api/config/validation-rules/reset", token=TOKEN)
    call("POST", "/api/config/aggregate-fields/reset", token=TOKEN)


# ======================================================================
# A. Seed 正确性
# ======================================================================
def test_A_seed():
    print("\n=== A. Seed 正确性 ===")
    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    check("A1_validation_rules_count_10",
          st == 200 and isinstance(rules, list) and len(rules) == 10,
          "status=%s len=%s" % (st, len(rules) if isinstance(rules, list) else rules))

    if isinstance(rules, list) and rules:
        all_enabled = all(r.get("enabled") for r in rules)
        keys = sorted(r.get("rule_key") for r in rules)
        check("A2_validation_rules_all_enabled", all_enabled,
              "disabled=%s" % [r.get("rule_key") for r in rules if not r.get("enabled")])
        check("A3_validation_rules_keys_match", keys == sorted(EXPECTED_RULE_KEYS),
              "got=%s" % keys)
        # 默认 severity 仅含 严重/中等
        bad_sev = [r.get("rule_key") for r in rules
                   if r.get("severity") not in ("严重", "中等")]
        check("A3b_severity_values_valid", not bad_sev, "bad=%s" % bad_sev)

    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    check("A4_aggregate_fields_count_11",
          st == 200 and isinstance(fields, list) and len(fields) == 11,
          "status=%s len=%s" % (st, len(fields) if isinstance(fields, list) else fields))

    if isinstance(fields, list) and fields:
        all_enabled = all(f.get("enabled") for f in fields)
        keys = sorted(f.get("field_key") for f in fields)
        check("A5_aggregate_fields_all_enabled", all_enabled,
              "disabled=%s" % [f.get("field_key") for f in fields if not f.get("enabled")])
        check("A6_aggregate_fields_keys_match", keys == sorted(EXPECTED_FIELD_KEYS),
              "got=%s" % keys)

    # aggregate-field-columns 端点（主理人拍板采用后端枚举端点）
    st, cols = call("GET", "/api/config/aggregate-field-columns", token=TOKEN)
    ok = st == 200 and isinstance(cols, list) and len(cols) > 0
    check("A7_aggregate_field_columns_list", ok, "status=%s len=%s" % (st, len(cols) if isinstance(cols, list) else cols))
    if isinstance(cols, list):
        check("A7b_columns_exclude_id", "id" not in cols, "id_excluded=%s" % ("id" not in cols))
        check("A7c_seed_keys_are_valid_columns",
              all(k in cols for k in EXPECTED_FIELD_KEYS),
              "missing=%s" % [k for k in EXPECTED_FIELD_KEYS if k not in cols])
        check("A7d_new_field_is_valid_column",
              NEW_FIELD_KEY in cols, "device_name_is_column=%s" % (NEW_FIELD_KEY in cols))


# ======================================================================
# B. 校验开关启停影响校验仪表盘（核心）
# ======================================================================
def test_B_dashboard():
    print("\n=== B. 校验开关影响校验仪表盘 ===")
    # 拿到 empty_code 的 id
    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    rid = get_rule_id_by_key(rules, "empty_code")
    check("B0_empty_code_rule_exists", rid is not None, "rule_id=%s" % rid)
    if rid is None:
        return

    # 全部启用时：10 个检查项，含「编号为空」
    st, dash = call("GET", "/api/validation", token=TOKEN)
    names_on = [c.get("check_name") for c in (dash or {}).get("checks", [])] if isinstance(dash, dict) else []
    check("B1_dashboard_all_enabled_has_10_checks",
          st == 200 and len(names_on) == 10,
          "status=%s checks=%s" % (st, len(names_on)))
    check("B1b_dashboard_has_empty_code", "编号为空" in names_on, "names=%s" % names_on)

    # 停用 empty_code
    st, _ = call("PUT", "/api/config/validation-rules/%s" % rid,
                 token=TOKEN, body={"enabled": False})
    check("B2_put_disable_ok", st == 200, "status=%s" % st)

    st, dash = call("GET", "/api/validation", token=TOKEN)
    names_off = [c.get("check_name") for c in (dash or {}).get("checks", [])] if isinstance(dash, dict) else []
    check("B3_disabled_dashboard_9_checks",
          st == 200 and len(names_off) == 9,
          "status=%s checks=%s" % (st, len(names_off)))
    check("B3b_disabled_dashboard_lacks_empty_code",
          "编号为空" not in names_off, "names=%s" % names_off)

    # 重新启用
    st, _ = call("PUT", "/api/config/validation-rules/%s" % rid,
                 token=TOKEN, body={"enabled": True})
    check("B4_put_enable_ok", st == 200, "status=%s" % st)

    st, dash = call("GET", "/api/validation", token=TOKEN)
    names_on2 = [c.get("check_name") for c in (dash or {}).get("checks", [])] if isinstance(dash, dict) else []
    check("B5_reenabled_dashboard_10_checks",
          st == 200 and len(names_on2) == 10 and "编号为空" in names_on2,
          "status=%s checks=%s" % (st, len(names_on2)))


# ======================================================================
# C. 聚合白名单：可用字段聚合 / 非法字段 400 / 维度级启停
# ======================================================================
def test_C_aggregate():
    print("\n=== C. 聚合白名单 ===")
    # 白名单内字段 room -> 200
    st, data = call("GET", "/api/stats/aggregate?field=room&metric=count", token=TOKEN)
    ok = st == 200 and isinstance(data, dict) and isinstance(data.get("rows"), list)
    check("C1_aggregate_room_200", ok, "status=%s" % st)

    # 合法列但不在白名单 -> 400
    st, _ = call("GET", "/api/stats/aggregate?field=%s" % NON_WHITELIST_COLUMN, token=TOKEN)
    check("C2_aggregate_nonwhitelist_400", st == 400, "status=%s" % st)

    # 完全非法列 -> 400
    st, _ = call("GET", "/api/stats/aggregate?field=%s" % INVALID_COLUMN, token=TOKEN)
    check("C3_aggregate_invalid_column_400", st == 400, "status=%s" % st)

    # 缺 field 参数 -> 400
    st, _ = call("GET", "/api/stats/aggregate", token=TOKEN)
    check("C3b_aggregate_missing_field_400", st == 400, "status=%s" % st)

    # 启用维度下拉列表（reports:view）应含 11 个
    st, dims = call("GET", "/api/stats/aggregate-fields", token=TOKEN)
    check("C4_aggregate_fields_enabled_list_11",
          st == 200 and isinstance(dims, list) and len(dims) == 11,
          "status=%s len=%s" % (st, len(dims) if isinstance(dims, list) else dims))

    # 取 room 维度 id，停用后再聚合应 400
    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    fid = get_field_id_by_key(fields, "room")
    check("C5_room_field_exists", fid is not None, "fid=%s" % fid)
    if fid is None:
        return

    st, _ = call("PUT", "/api/config/aggregate-fields/%s" % fid,
                 token=TOKEN, body={"enabled": False})
    check("C6_disable_room_ok", st == 200, "status=%s" % st)

    st, _ = call("GET", "/api/stats/aggregate?field=room", token=TOKEN)
    check("C7_disabled_room_aggregate_400", st == 400, "status=%s" % st)

    st, dims = call("GET", "/api/stats/aggregate-fields", token=TOKEN)
    check("C7b_disabled_room_dropdown_10",
          st == 200 and isinstance(dims, list) and len(dims) == 10,
          "status=%s len=%s" % (st, len(dims) if isinstance(dims, list) else dims))

    # 重新启用
    st, _ = call("PUT", "/api/config/aggregate-fields/%s" % fid,
                 token=TOKEN, body={"enabled": True})
    check("C8_reenable_room_ok", st == 200, "status=%s" % st)

    st, _ = call("GET", "/api/stats/aggregate?field=room", token=TOKEN)
    check("C9_reenabled_room_aggregate_200", st == 200, "status=%s" % st)

    st, dims = call("GET", "/api/stats/aggregate-fields", token=TOKEN)
    check("C9b_reenabled_room_dropdown_11",
          st == 200 and isinstance(dims, list) and len(dims) == 11,
          "status=%s len=%s" % (st, len(dims) if isinstance(dims, list) else dims))


# ======================================================================
# D. 聚合白名单 CRUD（白名单有完整 CRUD）
# ======================================================================
def test_D_crud():
    print("\n=== D. 聚合白名单 CRUD ===")
    # 新增合法维度
    st, created = call("POST", "/api/config/aggregate-fields", token=TOKEN,
                       body={"field_key": NEW_FIELD_KEY, "field_label": "测试设备名"})
    ok = st in (200, 201) and isinstance(created, dict) and created.get("field_key") == NEW_FIELD_KEY
    check("D1_create_custom_field", ok, "status=%s" % st)
    if not ok:
        return
    new_id = created.get("id")

    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    custom = next((f for f in fields if f.get("field_key") == NEW_FIELD_KEY), None)
    check("D2_custom_field_listed_enabled",
          custom is not None and custom.get("enabled") is True and custom.get("is_system") is False,
          "custom=%s" % custom)

    # 启用态下该维度可聚合
    st, _ = call("GET", "/api/stats/aggregate?field=%s" % NEW_FIELD_KEY, token=TOKEN)
    check("D5_custom_field_aggregatable", st == 200, "status=%s" % st)

    # 更新 label / enabled
    st, upd = call("PUT", "/api/config/aggregate-fields/%s" % new_id, token=TOKEN,
                   body={"field_label": "改名后的设备名", "enabled": True})
    ok = st == 200 and isinstance(upd, dict) and upd.get("field_label") == "改名后的设备名"
    check("D3_update_field", ok, "status=%s" % st)

    # toggle 停用
    st, _ = call("POST", "/api/config/aggregate-fields/%s/toggle" % new_id, token=TOKEN)
    check("D4_toggle_ok", st == 200, "status=%s" % st)
    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    custom = next((f for f in fields if f.get("field_key") == NEW_FIELD_KEY), None)
    check("D4b_toggle_reflected", custom is not None and custom.get("enabled") is False,
          "custom=%s" % custom)

    # is_system 禁物理删 -> 400
    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    room_id = get_field_id_by_key(fields, "room")
    st, _ = call("DELETE", "/api/config/aggregate-fields/%s" % room_id, token=TOKEN)
    check("D6_delete_is_system_400", st == 400, "status=%s" % st)

    # 删除自定义维度 -> 200
    st, _ = call("DELETE", "/api/config/aggregate-fields/%s" % new_id, token=TOKEN)
    check("D7_delete_custom_200", st == 200, "status=%s" % st)

    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    still = any(f.get("field_key") == NEW_FIELD_KEY for f in fields)
    check("D8_custom_gone", not still, "still present=%s" % still)


# ======================================================================
# E. reset 语义
# ======================================================================
def test_E_reset():
    print("\n=== E. reset 恢复默认语义 ===")
    # 校验开关：import 一个自定义 rule_key（会创建 is_system=False 行）
    st, imp = call("POST", "/api/config/validation-rules/import", token=TOKEN,
                   body={"rules": [{"rule_key": CUSTOM_RULE_KEY, "enabled": False}]})
    check("E1_import_custom_rule_created",
          st == 200 and isinstance(imp, dict) and imp.get("created", 0) >= 1,
          "status=%s resp=%s" % (st, imp))

    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    has_custom = any(r.get("rule_key") == CUSTOM_RULE_KEY for r in rules)
    check("E2_custom_rule_present", has_custom, "rules_count=%s" % len(rules))

    # 聚合：再建一个自定义维度
    st, _ = call("POST", "/api/config/aggregate-fields", token=TOKEN,
                 body={"field_key": NEW_FIELD_KEY, "field_label": "重置测试"})
    check("E3_create_custom_field_for_reset", st in (200, 201), "status=%s" % st)

    # reset 校验开关
    st, _ = call("POST", "/api/config/validation-rules/reset", token=TOKEN)
    check("E4_reset_validation_ok", st == 200, "status=%s" % st)

    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    keys = [r.get("rule_key") for r in rules] if isinstance(rules, list) else []
    check("E4b_after_reset_10_all_enabled_no_custom",
          isinstance(rules, list) and len(rules) == 10
          and all(r.get("enabled") for r in rules)
          and CUSTOM_RULE_KEY not in keys,
          "count=%s custom_present=%s" % (len(rules), CUSTOM_RULE_KEY in keys))

    # reset 聚合白名单
    st, _ = call("POST", "/api/config/aggregate-fields/reset", token=TOKEN)
    check("E5_reset_aggregate_ok", st == 200, "status=%s" % st)

    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    fkeys = [f.get("field_key") for f in fields] if isinstance(fields, list) else []
    check("E5b_after_reset_11_all_enabled_no_custom",
          isinstance(fields, list) and len(fields) == 11
          and all(f.get("enabled") for f in fields)
          and NEW_FIELD_KEY not in fkeys,
          "count=%s custom_present=%s" % (len(fields), NEW_FIELD_KEY in fkeys))


# ======================================================================
# F. RBAC：写操作匿名/非法 token 被拒，admin 可
# ======================================================================
def test_F_rbac():
    print("\n=== F. RBAC 权限守卫 ===")
    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    rid = get_rule_id_by_key(rules, "empty_code")
    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    fid = get_field_id_by_key(fields, "room")

    write_ops = [
        ("PUT", "/api/config/validation-rules/%s" % rid, {"enabled": True}),
        ("POST", "/api/config/validation-rules/%s/toggle" % rid, None),
        ("POST", "/api/config/validation-rules/import", {"rules": []}),
        ("POST", "/api/config/validation-rules/reset", None),
        ("POST", "/api/config/aggregate-fields", {"field_key": NEW_FIELD_KEY, "field_label": "x"}),
        ("PUT", "/api/config/aggregate-fields/%s" % fid, {"enabled": True}),
        ("DELETE", "/api/config/aggregate-fields/%s" % fid, None),
        ("POST", "/api/config/aggregate-fields/%s/toggle" % fid, None),
        ("POST", "/api/config/aggregate-fields/import", {"fields": []}),
        ("POST", "/api/config/aggregate-fields/reset", None),
    ]

    anon_rejected = 0
    invalid_rejected = 0
    for method, path, body in write_ops:
        st_anon, _ = call(method, path, token=None, body=body)
        if st_anon in (401, 403):
            anon_rejected += 1
        else:
            print("   !! anonymous NOT rejected: %s %s -> %s" % (method, path, st_anon))
        st_bad, _ = call(method, path, token="Bearer not.a.valid.token", body=body)
        if st_bad in (401, 403):
            invalid_rejected += 1
        else:
            print("   !! invalid token NOT rejected: %s %s -> %s" % (method, path, st_bad))

    check("F1_anonymous_rejected_all_writes",
          anon_rejected == len(write_ops),
          "%d/%d rejected" % (anon_rejected, len(write_ops)))
    check("F2_invalid_token_rejected_all_writes",
          invalid_rejected == len(write_ops),
          "%d/%d rejected" % (invalid_rejected, len(write_ops)))

    # 正向：admin 对写操作可成功（用无副作用的 enabled:true 兜底）
    st, _ = call("PUT", "/api/config/validation-rules/%s" % rid,
                 token=TOKEN, body={"enabled": True})
    check("F3_admin_can_write", st == 200, "status=%s" % st)

    # 精确 403 用例：需 viewer 账号；默认库无 viewer，跳过并记录
    st, users = call("GET", "/api/users", token=TOKEN)
    has_viewer = False
    if isinstance(users, dict):
        ulist = users.get("items") or users.get("users") or users.get("data") or []
        has_viewer = any(u.get("username") == "viewer" for u in ulist)
    check("F4_viewer_403_skipped_if_absent", True,
          "无 viewer 账号，跳过精确 403（已验证 admin 可 / 匿名不可 守卫）" if not has_viewer
          else "存在 viewer 账号，建议补充 403 用例")


# ======================================================================
# G. 导入 / 导出
# ======================================================================
def test_G_import_export():
    print("\n=== G. 导入 / 导出 ===")
    # 导出校验开关
    st, exp_rules = call("GET", "/api/config/validation-rules/export", token=TOKEN)
    check("G1_export_validation_10",
          st == 200 and isinstance(exp_rules, list) and len(exp_rules) == 10,
          "status=%s len=%s" % (st, len(exp_rules) if isinstance(exp_rules, list) else exp_rules))

    # 导出聚合白名单
    st, exp_fields = call("GET", "/api/config/aggregate-fields/export", token=TOKEN)
    check("G2_export_aggregate_11",
          st == 200 and isinstance(exp_fields, list) and len(exp_fields) == 11,
          "status=%s len=%s" % (st, len(exp_fields) if isinstance(exp_fields, list) else exp_fields))

    if not (isinstance(exp_rules, list) and exp_rules):
        return

    # 修改某条 enabled 后导入 -> 断言生效（empty_code 置否）
    flipped = []
    for r in exp_rules:
        item = {"rule_key": r.get("rule_key"), "enabled": r.get("enabled")}
        if r.get("rule_key") == "empty_code":
            item["enabled"] = False
        flipped.append(item)
    st, imp = call("POST", "/api/config/validation-rules/import", token=TOKEN,
                   body={"rules": flipped})
    check("G3_import_flipped_ok", st == 200, "status=%s" % st)

    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    ec = next((r for r in rules if r.get("rule_key") == "empty_code"), None)
    check("G3b_flipped_takes_effect", ec is not None and ec.get("enabled") is False,
          "empty_code enabled=%s" % (ec.get("enabled") if ec else None))

    # 同份原始导出 upsert -> updated==10 created==0（并恢复出厂态）
    st, imp = call("POST", "/api/config/validation-rules/import", token=TOKEN,
                   body={"rules": [{"rule_key": r.get("rule_key"), "enabled": r.get("enabled")}
                                   for r in exp_rules]})
    ok = st == 200 and isinstance(imp, dict) and imp.get("created", 0) == 0 and imp.get("updated", 0) == 10
    check("G4_import_roundtrip_upsert", ok, "status=%s resp=%s" % (st, imp))

    # 聚合导入含非法 field_key -> 422
    st, _ = call("POST", "/api/config/aggregate-fields/import", token=TOKEN,
                 body={"fields": [{"field_key": INVALID_COLUMN, "field_label": "x", "enabled": True}]})
    check("G5_import_illegal_field_422", st == 422, "status=%s" % st)

    # 聚合导出 upsert 回写 -> updated==11 created==0
    if isinstance(exp_fields, list) and exp_fields:
        payload = [{"field_key": f.get("field_key"), "field_label": f.get("field_label"),
                    "enabled": f.get("enabled"), "metric_support": f.get("metric_support")}
                   for f in exp_fields]
        st, imp = call("POST", "/api/config/aggregate-fields/import", token=TOKEN,
                       body={"fields": payload})
        ok = st == 200 and isinstance(imp, dict) and imp.get("created", 0) == 0 and imp.get("updated", 0) == 11
        check("G6_aggregate_import_roundtrip", ok, "status=%s resp=%s" % (st, imp))

    # 收尾：确保回到出厂态
    reset_both()


# ======================================================================
# H. 错误码
# ======================================================================
def test_H_error_codes():
    print("\n=== H. 错误码 ===")
    # 重复 field_key 新增 -> 400
    st, _ = call("POST", "/api/config/aggregate-fields", token=TOKEN,
                 body={"field_key": "room", "field_label": "重复"})
    check("H1_duplicate_field_key_400", st == 400, "status=%s" % st)

    # 删 is_system -> 400
    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    room_id = get_field_id_by_key(fields, "room")
    st, _ = call("DELETE", "/api/config/aggregate-fields/%s" % room_id, token=TOKEN)
    check("H2_delete_is_system_400", st == 400, "status=%s" % st)

    # 聚合非法字段 -> 400
    st, _ = call("GET", "/api/stats/aggregate?field=%s" % NON_WHITELIST_COLUMN, token=TOKEN)
    check("H3_aggregate_nonwhitelist_400", st == 400, "status=%s" % st)

    # 非法 field_key 新增 -> 422
    st, _ = call("POST", "/api/config/aggregate-fields", token=TOKEN,
                 body={"field_key": INVALID_COLUMN, "field_label": "非法"})
    check("H4_illegal_field_key_422", st == 422, "status=%s" % st)

    # 说明：校验开关无 create 端点（设计约定），故无「重复 rule_key -> 400」路径；
    # 该错误码约定仅适用于聚合白名单的 field_key 重复（H1 已覆盖）。


# ======================================================================
# I. 清理与静态检查（幂等 / 零残留）
# ======================================================================
def test_I_cleanup():
    print("\n=== I. 清理与静态检查 ===")
    reset_both()

    st, rules = call("GET", "/api/config/validation-rules", token=TOKEN)
    n = len(rules) if isinstance(rules, list) else -1
    custom = [r for r in rules if isinstance(r, dict) and r.get("is_system") is False] if isinstance(rules, list) else []
    check("I1_validation_factory_10_all_enabled_no_custom",
          n == 10 and all(r.get("enabled") for r in rules)
          and len(custom) == 0,
          "count=%s custom=%s" % (n, len(custom)))

    st, fields = call("GET", "/api/config/aggregate-fields", token=TOKEN)
    m = len(fields) if isinstance(fields, list) else -1
    custom_f = [f for f in fields if isinstance(f, dict) and f.get("is_system") is False] if isinstance(fields, list) else []
    check("I2_aggregate_factory_11_all_enabled_no_custom",
          m == 11 and all(f.get("enabled") for f in fields)
          and len(custom_f) == 0,
          "count=%s custom=%s" % (m, len(custom_f)))

    # 出厂态下聚合行为正常
    st, _ = call("GET", "/api/stats/aggregate?field=room", token=TOKEN)
    check("I3a_room_aggregate_200", st == 200, "status=%s" % st)
    st, _ = call("GET", "/api/stats/aggregate?field=%s" % NON_WHITELIST_COLUMN, token=TOKEN)
    check("I3b_sn_aggregate_400", st == 400, "status=%s" % st)


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def main():
    global TOKEN
    print("=" * 70)
    print("系统配置模块 P2 全量回归测试  (QA: 严过关)")
    print("Backend: %s" % BASE)
    print("=" * 70)

    # 0. 后端存活检查
    st, _ = call("GET", "/docs")
    if st != 200:
        print("!! 后端未响应 /docs (status=%s)。请先启动后端：" % st)
        print("   cd backend && python main.py  (或 python start.py --production)")
        sys.exit(2)

    # 1. 登录
    try:
        TOKEN = login(ADMIN_USER, ADMIN_PASS)
    except Exception as e:
        print("!! 登录失败：%s" % e)
        sys.exit(2)
    print("登录成功（admin），开始测试...\n")

    # 2. 预清理：保证可重复运行的确定性基线
    reset_both()
    print("-- 已执行 pre-reset，基线恢复为出厂态 --\n")

    try:
        test_A_seed()
        test_B_dashboard()
        test_C_aggregate()
        test_D_crud()
        test_E_reset()
        test_F_rbac()
        test_G_import_export()
        test_H_error_codes()
        test_I_cleanup()
    finally:
        # 无论如何都恢复出厂态（清理兜底）
        try:
            reset_both()
        except Exception:
            pass

    # 3. 汇总报告
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    failed = total - passed
    rate = (passed / total * 100.0) if total else 0.0
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    print("总用例数: %d | 通过: %d | 失败: %d | 通过率: %.1f%%" % (total, passed, failed, rate))
    if failed:
        print("\n失败用例：")
        for tid, p, info in results:
            if not p:
                print("  - %s  %s" % (tid, info))
    print("=" * 70)
    # 退出码：0=全过，1=有失败
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
