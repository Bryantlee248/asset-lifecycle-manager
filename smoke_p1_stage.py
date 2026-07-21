"""P1 最小冒烟测试（API 级）：list=11 / toggle→gate 行为变化 / export-import / 错误码。"""
import sys, os, json, urllib.request, urllib.error, urllib.parse

BASE = "http://127.0.0.1:8000"
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND)

import database as dbm
from database import SessionLocal, Asset


def http(method, path, token=None, body=None):
    url = BASE + urllib.parse.quote(path, safe="/?:=&")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


# 1) 登录 admin
st, admin = http("POST", "/api/auth/login", body={"username": "admin", "password": "Admin@2026!Secure"})
assert st == 200, f"login failed {st} {admin}"
token = admin["token"]
print("[OK] admin 登录成功")

# 2) list 规则 → 期望 11 条
st, rules = http("GET", "/api/config/stage-transitions", token=token)
assert st == 200, f"list failed {st} {rules}"
assert len(rules) == 11, f"期望 11 条 seed，实际 {len(rules)}"
print(f"[OK] GET /stage-transitions 返回 {len(rules)} 条 seed 规则")
print("   ", [(r["from_stage"], r["to_stage"], r["allowed"], r["require_inspection"], r["require_retirement"], r["require_location"], r["require_fault_record"]) for r in rules])

# 找一个 规划 阶段资产（调用 check_stage_gate 用）
db = SessionLocal()
plan_asset = db.query(Asset).filter(Asset.lifecycle_stage == "规划").first()
db.close()
assert plan_asset, "未找到 规划 阶段资产，无法验证 gate 行为"
code = plan_asset.asset_code
print(f"[OK] 取 规划 阶段资产用于 gate 验证: {code}")

# 3) toggle 前：规划→在途 应为允许
st, gate_before = http("GET", f"/api/assets/{code}/stage-gate/在途", token=token)
assert st == 200 and gate_before["allowed"] is True, f"toggle 前 gate 异常: {gate_before}"
print(f"[OK] toggle 前 规划→在途 gate: {gate_before['allowed']} / {gate_before['message']}")

# 定位 规划→在途 规则 id
rule = next(r for r in rules if r["from_stage"] == "规划" and r["to_stage"] == "在途")
rid = rule["id"]

# 4) toggle 关闭
st, toggled = http("POST", f"/api/config/stage-transitions/{rid}/toggle", token=token)
assert st == 200 and toggled["allowed"] is False, f"toggle 失败: {toggled}"
print(f"[OK] toggle 后 allowed={toggled['allowed']}")

# 5) toggle 后：规划→在途 应被拒（缓存已失效）
st, gate_after = http("GET", f"/api/assets/{code}/stage-gate/在途", token=token)
assert st == 200 and gate_after["allowed"] is False, f"toggle 后 gate 未变化: {gate_after}"
print(f"[OK] toggle 后 规划→在途 gate: {gate_after['allowed']} / {gate_after['message']}")

# 恢复（再 toggle 开）
st, _ = http("POST", f"/api/config/stage-transitions/{rid}/toggle", token=token)
print("[OK] 已恢复 规划→在途 为允许")

# 6) export
st, exported = http("GET", "/api/config/stage-transitions/export", token=token)
assert st == 200 and len(exported) == 11, f"export 异常: {st} {len(exported) if isinstance(exported, list) else exported}"
print(f"[OK] export 返回 {len(exported)} 条")

# 7) import（upsert 同一份）→ created=0, updated=11
st, imp = http("POST", "/api/config/stage-transitions/import", token=token, body={"rules": exported})
assert st == 200 and imp.get("created") == 0 and imp.get("updated") == 11, f"import 异常: {imp}"
print(f"[OK] import upsert 同份 → {imp}")

# 8) 错误码：非法阶段值 → 422
st, _ = http("POST", "/api/config/stage-transitions", token=token,
            body={"from_stage": "火星", "to_stage": "运行"})
assert st == 422, f"非法阶段应 422，实际 {st}"
print("[OK] 非法阶段值 POST → 422")

# 9) 错误码：重复 (规划,在途) → 400
st, _ = http("POST", "/api/config/stage-transitions", token=token,
            body={"from_stage": "规划", "to_stage": "在途"})
assert st == 400, f"重复对应 400，实际 {st}"
print("[OK] 重复 (规划,在途) POST → 400")

# 10) 权限：viewer 应 403（用 test_viewer 登录）
st, viewer = http("POST", "/api/auth/login", body={"username": "test_viewer", "password": "Test@2026!Pass"})
if st == 200:
    vtoken = viewer["token"]
    st2, _ = http("GET", "/api/config/stage-transitions", token=vtoken)
    assert st2 == 403, f"viewer 应 403，实际 {st2}"
    print("[OK] test_viewer 访问 → 403")
else:
    print(f"[SKIP] test_viewer 未创建（{st}）")

print("\n=== P1 冒烟全部通过 ===")
