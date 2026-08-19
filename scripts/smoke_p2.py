"""P2 最小冒烟脚本（工程师自验用，非 QA 回归脚本）。

覆盖设计 §8 错误码约定 + 主理人拍板语义：
  * 校验开关列表 10 全 enabled / 聚合白名单 11 全 enabled
  * 停用 empty_code 后 run_all_checks 不再含该项；恢复
  * 聚合 ?field=白名单字段 → 200；?field=不在白名单 → 400
  * reset 后回到出厂全开
  * 非法 field_key → 422；重复 field_key → 400；删 is_system → 400
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
ADMIN = ("admin", "Admin@2026!Secure")

results = []


def log(name, ok, detail=""):
    results.append((ok, name, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def req(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=10)
        return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode() or "{}")
        except Exception:
            payload = {}
        return e.code, payload


def main():
    # 1. 登录
    status, data = req("POST", "/api/auth/login", body={"username": ADMIN[0], "password": ADMIN[1]})
    if status != 200 or "token" not in data:
        log("login", False, f"status={status} data={data}")
        return
    token = data["token"]
    log("login", True, f"user={data.get('user',{}).get('username')}")

    # 2. 校验开关列表 10 全 enabled
    status, rules = req("GET", "/api/config/validation-rules", token)
    if status != 200 or len(rules) != 10:
        log("validation-rules list=10", False, f"status={status} len={len(rules) if isinstance(rules,list) else '?'}")
    else:
        all_on = all(r["enabled"] for r in rules)
        log("validation-rules list=10 & all enabled", all_on, f"count={len(rules)} all_on={all_on}")

    # 3. 聚合白名单 11 全 enabled
    status, fields = req("GET", "/api/config/aggregate-fields", token)
    if status != 200 or len(fields) != 11:
        log("aggregate-fields list=11", False, f"status={status} len={len(fields) if isinstance(fields,list) else '?'}")
    else:
        all_on = all(f["enabled"] for f in fields)
        log("aggregate-fields list=11 & all enabled", all_on, f"count={len(fields)} all_on={all_on}")

    # 3b. 后端枚举端点：候选列名（主理人拍板采用后端枚举端点）
    status, cols = req("GET", "/api/config/aggregate-field-columns", token)
    ok_cols = status == 200 and isinstance(cols, list) and "room" in cols and "asset_category_2" in cols
    log("aggregate-field-columns endpoint -> 200 & has valid cols", ok_cols, f"status={status} count={len(cols) if isinstance(cols,list) else '?'}")

    # 4. 停用 empty_code → 校验仪表盘消失该项；再恢复
    ec = next(r for r in rules if r["rule_key"] == "empty_code")
    status, _ = req("POST", f"/api/config/validation-rules/{ec['id']}/toggle", token)
    status, dash = req("GET", "/api/validation", token)
    keys_after_off = {c["check_name"] for c in dash.get("checks", [])}
    removed_ok = "编号为空" not in keys_after_off
    log("disable empty_code -> dashboard drops it", removed_ok, f"present_after_off={'编号为空' in keys_after_off}")
    # 恢复
    status, _ = req("POST", f"/api/config/validation-rules/{ec['id']}/toggle", token)
    status, dash = req("GET", "/api/validation", token)
    restored_ok = "编号为空" in {c["check_name"] for c in dash.get("checks", [])}
    log("re-enable empty_code -> dashboard shows it", restored_ok)

    # 5. 聚合接口：白名单字段 200 / 非白名单 400
    status, _ = req("GET", "/api/stats/aggregate?field=room&metric=count", token)
    log("aggregate field=room -> 200", status == 200, f"status={status}")
    status, _ = req("GET", "/api/stats/aggregate?field=not_a_real_column&metric=count", token)
    log("aggregate field=invalid -> 400", status == 400, f"status={status}")

    # 6. reset 后回到出厂全开
    status, _ = req("POST", "/api/config/validation-rules/reset", token)
    status, rules2 = req("GET", "/api/config/validation-rules", token)
    ok1 = status == 200 and len(rules2) == 10 and all(r["enabled"] for r in rules2)
    log("reset validation-rules -> 10 all enabled", ok1)
    status, _ = req("POST", "/api/config/aggregate-fields/reset", token)
    status, fields2 = req("GET", "/api/config/aggregate-fields", token)
    ok2 = status == 200 and len(fields2) == 11 and all(f["enabled"] for f in fields2)
    log("reset aggregate-fields -> 11 all enabled", ok2)

    # 7. 非法 field_key → 422；重复 → 400；删 is_system → 400
    status, _ = req("POST", "/api/config/aggregate-fields", token,
                    body={"field_key": "not_a_real_column", "field_label": "X"})
    log("create agg field illegal key -> 422", status == 422, f"status={status}")

    status, _ = req("POST", "/api/config/aggregate-fields", token,
                    body={"field_key": "room", "field_label": "机房"})
    log("create agg field duplicate key -> 400", status == 400, f"status={status}")

    # 找一个 is_system 行删除
    status, fields3 = req("GET", "/api/config/aggregate-fields", token)
    sys_row = next((f for f in fields3 if f["is_system"]), None)
    status, _ = req("DELETE", f"/api/config/aggregate-fields/{sys_row['id']}", token)
    log("delete is_system agg field -> 400", status == 400, f"status={status}")

    # 8. 新增合法非原 11 字段（O3）：department 已在 11 内，改用 asset_category_2（合法列名）验证新增路径
    status, created = req("POST", "/api/config/aggregate-fields", token,
                          body={"field_key": "asset_category_2", "field_label": "资产分类2", "remark": "smoke"})
    ok_create = status == 200 and created.get("field_key") == "asset_category_2"
    log("create agg field legal new column -> 200", ok_create, f"status={status}")
    if ok_create:
        # 该维度应可聚合
        status, _ = req("GET", "/api/stats/aggregate?field=asset_category_2&metric=count", token)
        log("aggregate new field -> 200", status == 200, f"status={status}")
        # 清理：删除自定义行（非 is_system 可删）
        status, _ = req("DELETE", f"/api/config/aggregate-fields/{created['id']}", token)
        log("delete custom agg field -> 200", status == 200, f"status={status}")
        # 复位
        req("POST", "/api/config/aggregate-fields/reset", token)

    print("\n==== SUMMARY ====")
    passed = sum(1 for ok, _, _ in results if ok)
    print(f"{passed}/{len(results)} checks passed")
    if passed != len(results):
        print("FAILED CHECKS:")
        for ok, name, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")


if __name__ == "__main__":
    main()
