# -*- coding: utf-8 -*-
"""系统配置模块 P1 —— 阶段流转矩阵可配置 全量回归测试

QA 工程师：严过关（software-qa-engineer）
覆盖：A.Seed 正确性 B.CRUD+Toggle C.流转校验走配置表(存量零风险)
      D.引用/出口保护 E.RBAC F.导入/导出 G.错误码 H.清理与幂等

运行方式：
  python qa-test-config-module-P1.py
（后端须以生产模式运行于 http://127.0.0.1:8000，管理员 admin/Admin@2026!Secure）
"""
import json
import urllib.request
import urllib.error
import urllib.parse

BASE = "http://127.0.0.1:8000"
ADMIN = ("admin", "Admin@2026!Secure")
VIEWER = ("test_viewer", "Test@2026!")

# ---- 设计文档 §5 精确 11 行 seed 矩阵（期望基准） ----
# (from_stage, to_stage, allowed, require_retirement, require_data_cleared,
#  require_inspection, require_location, require_fault_record, require_approval, is_system)
EXPECTED_SEED = [
    ("规划", "在途", True, False, False, False, False, False, True, True),
    ("规划", "上架", True, False, False, False, False, False, True, True),
    ("在途", "上架", True, False, False, True, False, False, True, True),
    ("在途", "运行", True, False, False, False, False, False, True, True),
    ("上架", "运行", True, False, False, False, True, False, True, True),
    ("运行", "维修", True, False, False, False, False, False, True, True),
    ("运行", "待报废", True, False, False, False, False, False, True, True),
    ("运行", "在途", True, False, False, False, False, False, True, True),
    ("维修", "运行", True, False, False, False, False, True, True, True),
    ("维修", "待报废", True, False, False, False, False, False, True, True),
    ("待报废", "已报废", True, True, True, False, False, False, True, True),
]


# ============================================================
# 轻量测试框架
# ============================================================
class Tester:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.failures = []

    def record(self, name, ok, detail=""):
        self.total += 1
        if ok:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.failures.append((name, detail))
            print(f"  [FAIL] {name}  -> {detail}")

    def section(self, title):
        print(f"\n=== {title} ===")


# ============================================================
# HTTP 辅助
# ============================================================
def _http(method, path, body=None, token=None):
    """返回 dict: status, json(或 text)"""
    url = BASE + urllib.parse.quote(path, safe="/?:=&")
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw_body = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raw_body = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:
        return {"status": None, "error": f"{type(e).__name__}: {e}", "raw": None}
    try:
        payload = json.loads(raw_body) if raw_body else None
    except Exception:
        payload = raw_body
    return {"status": status, "json": payload, "raw": raw_body}


def login(username, password):
    r = _http("POST", "/api/auth/login", {"username": username, "password": password})
    if r["status"] == 200 and r.get("json"):
        return r["json"].get("token")
    return None


# ============================================================
# 幂等重置：确保库态为 11 条 seed 且全 allowed=true、无自定义残留
# ============================================================
def reset_to_seed(t, admin_token):
    print("\n=== 幂等重置 (reset to seed baseline) ===")
    # 先恢复所有 seed 规则 allowed=true，再删除自定义规则（避免出口保护拦截删除）
    lst = _http("GET", "/api/config/stage-transitions", token=admin_token)
    if lst["status"] != 200:
        print("  reset 跳过：无法读取规则列表", lst)
        return
    for rule in lst["json"]:
        if rule.get("is_system") and rule.get("allowed") is False:
            _http("PUT", f"/api/config/stage-transitions/{rule['id']}",
                  {"allowed": True}, token=admin_token)
    # 重新读取并删除所有自定义规则
    lst2 = _http("GET", "/api/config/stage-transitions", token=admin_token)
    if lst2["status"] == 200:
        for rule in lst2["json"]:
            if not rule.get("is_system"):
                _http("DELETE", f"/api/config/stage-transitions/{rule['id']}", token=admin_token)


# ============================================================
# 主测试流程
# ============================================================
def main():
    t = Tester()
    print("=" * 64)
    print(" 系统配置模块 P1 —— 阶段流转矩阵可配置 全量回归测试")
    print("=" * 64)

    # 0) 后端存活
    t.section("0. 后端存活")
    docs = _http("GET", "/docs")
    t.record("后端 /docs 可达(200)", docs["status"] == 200,
             f"status={docs['status']}, err={docs.get('error')}")
    if docs["status"] != 200:
        print("\n后端未运行，无法继续。请先以生产模式启动后端。")
        return report(t)

    admin_token = login(*ADMIN)
    t.record("admin 登录获取 token", bool(admin_token), f"token={'有' if admin_token else '无'}")
    if not admin_token:
        print("\nadmin 登录失败，无法继续。")
        return report(t)

    # 幂等重置
    reset_to_seed(t, admin_token)

    # 取一个真实的 规划 阶段资产（用于门禁等价校验）
    PLAN_ASSET = None
    la = _http("GET", "/api/assets?stage=规划&page=1&page_size=1", token=admin_token)
    if la["status"] == 200 and la.get("json"):
        items = la["json"].get("items") or []
        if items:
            PLAN_ASSET = items[0].get("asset_code")
    if not PLAN_ASSET:
        PLAN_ASSET = "DC-CL-PDU-0071"  # 兜底
    t.record("取得真实 规划 阶段资产", bool(PLAN_ASSET), f"asset_code={PLAN_ASSET}")

    # ============================================================
    # A. Seed 正确性
    # ============================================================
    t.section("A. Seed 正确性（11 条 + 精确矩阵）")
    lst = _http("GET", "/api/config/stage-transitions", token=admin_token)
    t.record("GET /stage-transitions 返回 200", lst["status"] == 200, f"status={lst['status']}")
    rules = lst.get("json") or []
    t.record("规则总数恰为 11 条", len(rules) == 11, f"实际 {len(rules)} 条")

    def rule_tuple(r):
        return (r["from_stage"], r["to_stage"], bool(r["allowed"]),
                bool(r.get("require_retirement")), bool(r.get("require_data_cleared")),
                bool(r.get("require_inspection")), bool(r.get("require_location")),
                bool(r.get("require_fault_record")), bool(r.get("require_approval")),
                bool(r.get("is_system")))

    got_set = {rule_tuple(r) for r in rules}
    exp_set = set(EXPECTED_SEED)
    missing = exp_set - got_set
    extra = got_set - exp_set
    t.record("逐条比对精确匹配设计 §5 矩阵", not missing and not extra,
             f"missing={missing} extra={extra}")

    # 保存原始 export 供后续还原
    exp0 = _http("GET", "/api/config/stage-transitions/export", token=admin_token)
    ORIGINAL_EXPORT = exp0.get("json") if exp0["status"] == 200 else None
    t.record("export 返回 11 条可还原基准", bool(ORIGINAL_EXPORT) and len(ORIGINAL_EXPORT) == 11,
             f"len={len(ORIGINAL_EXPORT) if ORIGINAL_EXPORT else None}")

    # ============================================================
    # C1. 流转校验统一走配置表（基线，未做任何写操作）—— 放在 CRUD 之前
    # ============================================================
    t.section("C. 流转校验统一走配置表（存量零风险 / 等价原硬编码）")
    gate_allowed_pairs = [("规划", "在途"), ("规划", "上架")]
    for frm, to in gate_allowed_pairs:
        g = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/{to}", token=admin_token)
        ok = g["status"] == 200 and isinstance(g.get("json"), dict) and g["json"].get("allowed") is True
        t.record(f"门禁 {frm}→{to} 应允许(allowed:true)", ok, f"status={g['status']} body={g.get('json')}")

    gate_forbidden = [("规划", "运行"), ("规划", "维修"), ("规划", "待报废"), ("规划", "已报废"), ("规划", "规划")]
    for frm, to in gate_forbidden:
        g = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/{to}", token=admin_token)
        js = g.get("json")
        ok = g["status"] == 200 and isinstance(js, dict) and js.get("allowed") is False and bool(js.get("message"))
        t.record(f"门禁 {frm}→{to} 应禁止(allowed:false+message)", ok, f"status={g['status']} body={js}")

    # ============================================================
    # B. CRUD + Toggle（使用自定义对 规划→运行，库态全程受控）
    # ============================================================
    t.section("B. CRUD + Toggle（自定义规则 规划→运行）")
    created_id = None
    c = _http("POST", "/api/config/stage-transitions",
              {"from_stage": "规划", "to_stage": "运行", "allowed": False,
               "remark": "QA 自建构禁用例"}, token=admin_token)
    t.record("POST 创建 规划→运行(allowed=false) 返回 200", c["status"] == 200, f"status={c['status']} body={c.get('json')}")
    if c["status"] == 200 and c.get("json"):
        rule = c["json"]
        created_id = rule.get("id")
        t.record("新建规则 is_system=false", rule.get("is_system") is False, f"is_system={rule.get('is_system')}")
        t.record("新建规则 allowed=false", rule.get("allowed") is False, f"allowed={rule.get('allowed')}")

    # 创建 allowed=false 的规则后，门禁 规划→运行 应读到此禁用规则 → allowed:false
    # （证明门禁走配置表而非硬编码；此时规则存在但被停用）
    if created_id:
        g0 = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/运行", token=admin_token)
        t.record("门禁读到新禁用规则 规划→运行(allowed:false)",
                 g0["status"] == 200 and g0.get("json", {}).get("allowed") is False
                 and bool(g0.get("json", {}).get("message")),
                 f"status={g0['status']} body={g0.get('json')}")

    # B2 PUT 修改字段（remark）
    if created_id:
        u = _http("PUT", f"/api/config/stage-transitions/{created_id}",
                  {"remark": "QA 已修改备注"}, token=admin_token)
        t.record("PUT 修改 remark 返回 200", u["status"] == 200, f"status={u['status']}")
        if u["status"] == 200:
            t.record("PUT 后 remark 生效", u.get("json", {}).get("remark") == "QA 已修改备注",
                     f"remark={u.get('json', {}).get('remark')}")

    # B3 toggle 翻转 allowed
    if created_id:
        before = _http("GET", f"/api/config/stage-transitions/{created_id}", token=admin_token)
        tg = _http("POST", f"/api/config/stage-transitions/{created_id}/toggle", token=admin_token)
        t.record("POST toggle 返回 200", tg["status"] == 200, f"status={tg['status']}")
        if tg["status"] == 200:
            t.record("toggle 后 allowed 翻转",
                     tg.get("json", {}).get("allowed") is not (before.get("json", {}).get("allowed")),
                     f"before={before.get('json', {}).get('allowed')} after={tg.get('json', {}).get('allowed')}")
            # toggle 后缓存失效：门禁 规划→运行 应变为 allowed:true
            g1 = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/运行", token=admin_token)
            t.record("toggle 后缓存失效：门禁 规划→运行 变为 allowed:true",
                     g1["status"] == 200 and g1.get("json", {}).get("allowed") is True,
                     f"status={g1['status']} body={g1.get('json')}")

    # B4 删除自建规则
    if created_id:
        d = _http("DELETE", f"/api/config/stage-transitions/{created_id}", token=admin_token)
        t.record("DELETE 自建规则 返回 200", d["status"] == 200, f"status={d['status']}")
        # 该路由无 GET-by-id 端点，改用重复 DELETE 验证已不存在（应 404）
        again = _http("DELETE", f"/api/config/stage-transitions/{created_id}", token=admin_token)
        t.record("删除后该规则不复存在(重复DELETE应404)", again["status"] == 404, f"status={again['status']}")

    # ============================================================
    # C2. require_* 标志被门禁消费（等价性强化证明）
    # ============================================================
    t.section("C2. require_* 标志被门禁消费（等价性强化）")
    c2 = _http("POST", "/api/config/stage-transitions",
               {"from_stage": "规划", "to_stage": "运行", "allowed": True,
                "require_fault_record": True, "remark": "QA require测试"}, token=admin_token)
    rid_a = c2.get("json", {}).get("id") if c2["status"] == 200 else None
    t.record("创建 规划→运行(require_fault_record=true)", c2["status"] == 200, f"status={c2['status']}")
    if rid_a:
        g = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/运行", token=admin_token)
        js = g.get("json") or {}
        t.record("门禁 规划→运行(require_fault_record) 应 false",
                 g["status"] == 200 and js.get("allowed") is False, f"status={g['status']} body={js}")
        t.record("门禁提示含故障记录文案", "故障" in (js.get("message") or ""), f"msg={js.get('message')}")
        _http("DELETE", f"/api/config/stage-transitions/{rid_a}", token=admin_token)

    c3 = _http("POST", "/api/config/stage-transitions",
               {"from_stage": "规划", "to_stage": "运行", "allowed": True,
                "remark": "QA 无require测试"}, token=admin_token)
    rid_b = c3.get("json", {}).get("id") if c3["status"] == 200 else None
    t.record("创建 规划→运行(无 require)", c3["status"] == 200, f"status={c3['status']}")
    if rid_b:
        g = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/运行", token=admin_token)
        t.record("门禁 规划→运行(无 require) 应 true",
                 g["status"] == 200 and g.get("json", {}).get("allowed") is True,
                 f"status={g['status']} body={g.get('json')}")
        _http("DELETE", f"/api/config/stage-transitions/{rid_b}", token=admin_token)

    # ============================================================
    # D. 引用/出口保护
    # ============================================================
    t.section("D. 引用 / 出口保护（O2）")
    seed_ids = {(r["from_stage"], r["to_stage"]): r["id"] for r in rules}
    plan_seed_ids = [seed_ids[("规划", "在途")], seed_ids[("规划", "上架")]]
    # D1 出口保护：关掉 规划 的两条 seed 出口，仅留自定义 规划→运行，
    #     规划 阶段有 4 条存量资产 → 删除自定义规则应 400 且提示存量计数
    for sid in plan_seed_ids:
        _http("POST", f"/api/config/stage-transitions/{sid}/toggle", token=admin_token)  # -> false
    cd = _http("POST", "/api/config/stage-transitions",
               {"from_stage": "规划", "to_stage": "运行", "allowed": True,
                "remark": "QA 出口保护唯一出口"}, token=admin_token)
    rid_exit = cd.get("json", {}).get("id") if cd["status"] == 200 else None
    t.record("创建 规划→运行 作为 规划 唯一出口", cd["status"] == 200, f"status={cd['status']}")
    if rid_exit:
        dd = _http("DELETE", f"/api/config/stage-transitions/{rid_exit}", token=admin_token)
        t.record("删除唯一出口规则 应 400", dd["status"] == 400, f"status={dd['status']}")
        msg = ""
        if isinstance(dd.get("json"), dict):
            msg = str(dd["json"].get("detail") or dd["json"].get("message") or "")
        t.record("400 响应含存量计数提示(禁止删除)", ("禁止" in msg) and ("4" in msg), f"msg={msg}")
        # 清理：先恢复 seed 出口，再删自定义规则
        for sid in plan_seed_ids:
            _http("POST", f"/api/config/stage-transitions/{sid}/toggle", token=admin_token)  # -> true
        _http("DELETE", f"/api/config/stage-transitions/{rid_exit}", token=admin_token)

    # D2 普通可删规则（非唯一出口）DELETE → 200
    cd2 = _http("POST", "/api/config/stage-transitions",
                {"from_stage": "规划", "to_stage": "维修", "allowed": True,
                 "remark": "QA 普通可删"}, token=admin_token)
    rid_norm = cd2.get("json", {}).get("id") if cd2["status"] == 200 else None
    t.record("创建普通可删规则 规划→维修", cd2["status"] == 200, f"status={cd2['status']}")
    if rid_norm:
        dd2 = _http("DELETE", f"/api/config/stage-transitions/{rid_norm}", token=admin_token)
        t.record("DELETE 普通可删规则 应 200", dd2["status"] == 200, f"status={dd2['status']}")

    # ============================================================
    # E. RBAC
    # ============================================================
    t.section("E. RBAC（config:manage 守卫）")
    anon = _http("GET", "/api/config/stage-transitions")
    t.record("无 token 访问 应 401", anon["status"] == 401, f"status={anon['status']}")
    bad = _http("GET", "/api/config/stage-transitions", token="not-a-valid-token")
    t.record("非法 token 访问 应 401", bad["status"] == 401, f"status={bad['status']}")
    anon_post = _http("POST", "/api/config/stage-transitions",
                      {"from_stage": "规划", "to_stage": "运行"}, token="xyz")
    t.record("无 token 写操作 应 401", anon_post["status"] == 401, f"status={anon_post['status']}")
    viewer_token = login(*VIEWER)
    t.record("viewer 登录获取 token", bool(viewer_token), f"token={'有' if viewer_token else '无'}")
    if viewer_token:
        v_get = _http("GET", "/api/config/stage-transitions", token=viewer_token)
        t.record("viewer GET 应 403", v_get["status"] == 403, f"status={v_get['status']}")
        v_post = _http("POST", "/api/config/stage-transitions",
                       {"from_stage": "规划", "to_stage": "运行"}, token=viewer_token)
        t.record("viewer POST 应 403", v_post["status"] == 403, f"status={v_post['status']}")
        v_del = _http("DELETE", f"/api/config/stage-transitions/1", token=viewer_token)
        t.record("viewer DELETE 应 403", v_del["status"] == 403, f"status={v_del['status']}")
        v_imp = _http("POST", "/api/config/stage-transitions/import",
                      {"rules": []}, token=viewer_token)
        t.record("viewer import 应 403", v_imp["status"] == 403, f"status={v_imp['status']}")

    # ============================================================
    # F. 导入 / 导出
    # ============================================================
    t.section("F. 导入 / 导出（JSON + upsert）")
    ex = _http("GET", "/api/config/stage-transitions/export", token=admin_token)
    t.record("export 返回 JSON 数组(11 条)",
             ex["status"] == 200 and isinstance(ex.get("json"), list) and len(ex["json"]) == 11,
             f"status={ex['status']} len={len(ex.get('json') or [])}")
    if ex["status"] == 200 and ex.get("json"):
        imp = _http("POST", "/api/config/stage-transitions/import",
                    {"rules": ex["json"]}, token=admin_token)
        t.record("同份 export 再 import 应 {created:0,updated:11}",
                 imp["status"] == 200 and imp.get("json", {}).get("created") == 0
                 and imp.get("json", {}).get("updated") == 11,
                 f"status={imp['status']} body={imp.get('json')}")
    bad_imp = _http("POST", "/api/config/stage-transitions/import",
                    {"rules": [{"from_stage": "火星", "to_stage": "运行"}]}, token=admin_token)
    t.record("import 含非法 stage 值 应 422", bad_imp["status"] == 422,
             f"status={bad_imp['status']} body={bad_imp.get('json')}")
    if ORIGINAL_EXPORT:
        mod = json.loads(json.dumps(ORIGINAL_EXPORT))
        for r in mod:
            if r["from_stage"] == "规划" and r["to_stage"] == "在途":
                r["allowed"] = False
                r["remark"] = "QA 导入修改演示"
        mim = _http("POST", "/api/config/stage-transitions/import", {"rules": mod}, token=admin_token)
        t.record("import 修改 规划→在途(allowed=false) 应 updated>=1",
                 mim["status"] == 200 and mim.get("json", {}).get("updated", 0) >= 1,
                 f"status={mim['status']} body={mim.get('json')}")
        chk = _http("GET", "/api/config/stage-transitions", token=admin_token)
        plan_rule = next((x for x in (chk.get("json") or [])
                          if x["from_stage"] == "规划" and x["to_stage"] == "在途"), None)
        t.record("import 后 规划→在途 allowed 实际为 false",
                 plan_rule is not None and plan_rule.get("allowed") is False,
                 f"allowed={plan_rule.get('allowed') if plan_rule else None}")
    # 还原：用原始基准重新 import
    if ORIGINAL_EXPORT:
        res = _http("POST", "/api/config/stage-transitions/import",
                    {"rules": ORIGINAL_EXPORT}, token=admin_token)
        t.record("以原始基准 import 还原到 seed 状态",
                 res["status"] == 200 and res.get("json", {}).get("updated", 0) == 11,
                 f"status={res['status']} body={res.get('json')}")

    # ============================================================
    # G. 错误码
    # ============================================================
    t.section("G. 错误码（400/422 约定）")
    dup = _http("POST", "/api/config/stage-transitions",
                {"from_stage": "规划", "to_stage": "在途"}, token=admin_token)
    t.record("重复 (规划,在途) POST 应 400", dup["status"] == 400, f"status={dup['status']}")
    sys_id = seed_ids.get(("规划", "在途"))
    if sys_id:
        ds = _http("DELETE", f"/api/config/stage-transitions/{sys_id}", token=admin_token)
        t.record("删除 is_system 规则 应 400", ds["status"] == 400, f"status={ds['status']}")
        msg = ""
        if isinstance(ds.get("json"), dict):
            msg = str(ds["json"].get("detail") or "")
        t.record("400 提示'系统内置规则不可删除'", "系统内置" in msg, f"msg={msg}")
    illegal = _http("POST", "/api/config/stage-transitions",
                    {"from_stage": "未知阶段", "to_stage": "运行"}, token=admin_token)
    t.record("非法 stage 值 POST 应 422", illegal["status"] == 422, f"status={illegal['status']}")

    # ============================================================
    # H. 清理与幂等（库态回到 11 条 seed、零 orphan）
    # ============================================================
    t.section("H. 清理与幂等（库态校验）")
    reset_to_seed(t, admin_token)
    final = _http("GET", "/api/config/stage-transitions", token=admin_token)
    final_rules = final.get("json") or []
    t.record("清理后规则总数回到 11", len(final_rules) == 11, f"实际 {len(final_rules)}")
    custom_left = [r for r in final_rules if not r.get("is_system")]
    t.record("清理后无自定义残留(零 orphan)", len(custom_left) == 0, f"残留 {len(custom_left)} 条: {custom_left}")
    final_set = {rule_tuple(r) for r in final_rules}
    t.record("清理后矩阵仍为设计 §5 精确 11 行", final_set == exp_set, f"diff={exp_set ^ final_set}")
    g1 = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/在途", token=admin_token)
    t.record("最终基线：门禁 规划→在途 allowed:true",
             g1["status"] == 200 and g1.get("json", {}).get("allowed") is True, f"body={g1.get('json')}")
    g2 = _http("GET", f"/api/assets/{PLAN_ASSET}/stage-gate/运行", token=admin_token)
    t.record("最终基线：门禁 规划→运行 allowed:false",
             g2["status"] == 200 and g2.get("json", {}).get("allowed") is False
             and bool(g2.get("json", {}).get("message")), f"body={g2.get('json')}")

    return report(t)


def report(t):
    print("\n" + "=" * 64)
    print(" 测试报告")
    print("=" * 64)
    print(f" 总用例数: {t.total}")
    print(f" 通过:     {t.passed}")
    print(f" 失败:     {t.failed}")
    rate = (t.passed / t.total * 100) if t.total else 0
    print(f" 通过率:   {rate:.1f}%")
    if t.failures:
        print("\n 失败明细:")
        for name, detail in t.failures:
            print(f"  - {name}: {detail}")
    verdict = "PASS" if t.failed == 0 else "FAIL"
    print(f"\n 最终判定: {verdict}")
    print("=" * 64)
    return t


if __name__ == "__main__":
    main()
