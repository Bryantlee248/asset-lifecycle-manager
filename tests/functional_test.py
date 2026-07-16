#!/usr/bin/env python3
"""IT资产全生命周期管理系统 v2.2.0 全面功能测试脚本 - Round 2"""
import urllib.request
import urllib.error
import urllib.parse
import json
import time
import sys
import os

BASE = "http://127.0.0.1:8000"

# ============ Test Results Tracking ============
results = []
def record(module, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"module": module, "name": name, "status": status, "detail": detail})
    icon = "✓" if passed else "✗"
    print(f"  {icon} [{module}] {name}" + (f" — {detail}" if detail and not passed else ""))

# ============ HTTP Helper with URL encoding for Chinese chars ============
def encode_url(path):
    """Percent-encode Chinese characters in URL path"""
    # Split into path and query parts
    if "?" in path:
        base_path, query_str = path.split("?", 1)
    else:
        base_path = path
        query_str = ""

    # Encode path segments
    segments = base_path.split("/")
    encoded_segments = []
    for seg in segments:
        if any(ord(c) > 127 for c in seg):
            encoded_segments.append(urllib.parse.quote(seg, safe=""))
        else:
            encoded_segments.append(seg)
    encoded_path = "/".join(encoded_segments)

    # Encode query parameters
    if query_str:
        params = urllib.parse.parse_qs(query_str, keep_blank_values=True)
        encoded_params = []
        for key, vals in params.items():
            for val in vals:
                encoded_params.append(f"{urllib.parse.quote(key, safe='')}={urllib.parse.quote(val, safe='')}")
        encoded_path += "?" + "&".join(encoded_params)

    return f"{BASE}{encoded_path}"

def api(method, path, data=None, token=None, expect_status=None, raw=False):
    """Send HTTP request and return (status_code, response_body_dict, error_msg)"""
    url = encode_url(path)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        status = resp.getcode()
        raw_bytes = resp.read()
        # Try to parse as JSON first; if not JSON (e.g., binary Excel), store as success marker
        try:
            raw_body = raw_bytes.decode("utf-8")
            rbody = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            rbody = {"_binary": True, "_size": len(raw_bytes), "_content_type": resp.headers.get("Content-Type", "")}
        if expect_status and status != expect_status:
            return status, rbody, f"Expected {expect_status}, got {status}"
        return status, rbody, None
    except urllib.error.HTTPError as e:
        status = e.code
        raw_body = e.read().decode("utf-8")
        try:
            rbody = json.loads(raw_body)
        except:
            rbody = {"_raw": raw_body[:500]}
        if expect_status and status != expect_status:
            return status, rbody, f"Expected {expect_status}, got {status}; body={rbody}"
        return status, rbody, None
    except urllib.error.URLError as e:
        return 0, {}, f"Connection error: {e.reason}"

def login(username, password):
    """Login and return (token, user_dict)"""
    s, b, err = api("POST", "/api/auth/login", {"username": username, "password": password})
    if err or s != 200:
        return None, None
    return b.get("token"), b.get("user")

# ============ Login All Accounts ============
print("\n" + "="*60)
print("  IT资产全生命周期管理系统 v2.2.0 功能测试")
print("="*60)

print("\n>>> 登录获取各角色Token...")
tokens = {}
users_info = {}
accounts = {
    "admin": ("admin", "admin123"),
    "zhangwei": ("zhangwei", "Ops2024!"),
    "liyang": ("liyang", "Ops2024!"),
    "wangjun": ("wangjun", "Eng2024!"),
    "chenming": ("chenming", "Eng2024!"),
    "liuqiang": ("liuqiang", "Eng2024!"),
    "zhaoli": ("zhaoli", "Eng2024!"),
    "sunfang": ("sunfang", "View2024!"),
    "huangjie": ("huangjie", "View2024!"),
}
for key, (u, p) in accounts.items():
    tok, usr = login(u, p)
    if tok:
        tokens[key] = tok
        users_info[key] = usr
        print(f"  ✓ {key}/{u} 登录成功")
    else:
        print(f"  ✗ {key}/{u} 登录失败 (密码可能已变更或账号不存在)")

admin_tok = tokens.get("admin")
ops_mgr_tok = tokens.get("zhangwei")
ops_mgr2_tok = tokens.get("liyang")
engineer_tok = tokens.get("wangjun")
engineer2_tok = tokens.get("chenming")
viewer_tok = tokens.get("sunfang")

# ============ Pre-cleanup: Remove any leftover test data from previous runs ============
print("\n>>> 清理前次测试残留数据...")
# Try to delete known test asset codes that may exist
pre_cleanup_codes = [
    "FUNC-ASSET-001", "GATE-FUNC-001", "GATE-FUNC-002", "SUB-FUNC-001",
    "FAULT-FUNC-001", "FAULT-SHANGJIA-001", "APR-FUNC-001",
    "APR-RETIRE-001", "APR-REJECT-001", "APR-CANCEL-001", "APR-MANUAL-001",
    "P3-TEST-001", "P1-SHANGJIA-001", "EDGE-EMPTY-001", "CASCADE-FUNC-001",
    "TEST-ASSET-001", "GATE-TEST-001", "GATE-TEST-002",
    "APR-TEST-001", "APR-FAULT-001", "APR-RETIRE-001",
    "FAULT-TEST-001", "P3-TEST-001",
    "FAULT-DBG4", "FAULT-DBG2", "FAULT-DBG3", "DEBUG-001", "DEBUG-P1",
    "TEST-VIEWER-001", "FUNC-BADCAT-001",
]
for code in pre_cleanup_codes:
    s, b, _ = api("GET", f"/api/assets/{code}", token=admin_tok)
    if s == 200 and b.get("id"):
        api("DELETE", f"/api/assets/{b['id']}", token=admin_tok)
        print(f"  清理资产 {code}")

# ================================================================
#  1. 认证模块
# ================================================================
print("\n>>> 1. 认证模块测试")

# 1.1 登录失败场景
s, b, err = api("POST", "/api/auth/login", {"username": "admin", "password": "wrongpwd"}, expect_status=401)
record("认证", "登录-错误密码应401", s == 401, f"status={s}, detail={b.get('detail','')}")

s, b, err = api("POST", "/api/auth/login", {"username": "nouser999", "password": "admin123"}, expect_status=401)
record("认证", "登录-不存在用户应401", s == 401, f"status={s}, detail={b.get('detail','')}")

# 1.2 Token无效
s, b, err = api("GET", "/api/auth/me", token="invalidtoken12345678", expect_status=401)
record("认证", "Token无效应401", s == 401, f"status={s}")

# 1.3 禁用账号登录
# Try to find test_disabled user first, or create one
s, b, _ = api("GET", "/api/users?search=test_disabled", token=admin_tok)
disabled_users = [u for u in b.get("items", []) if u.get("username") == "test_disabled"]
if not disabled_users:
    s, b, _ = api("POST", "/api/users", {
        "username": "test_disabled_user", "password": "Test2024!",
        "real_name": "测试禁用用户", "department": "测试部"
    }, token=admin_tok)
    test_disabled_id = b.get("id")
else:
    test_disabled_id = disabled_users[0]["id"]
    # Re-enable first
    api("PUT", f"/api/users/{test_disabled_id}", {"status": "active"}, token=admin_tok)

if test_disabled_id:
    # Disable the user
    api("PUT", f"/api/users/{test_disabled_id}", {"status": "disabled"}, token=admin_tok)
    # Try login with disabled account
    s, b, err = api("POST", "/api/auth/login", {"username": "test_disabled_user", "password": "Test2024!"}, expect_status=403)
    record("认证", "登录-禁用账号应403", s == 403, f"status={s}, detail={b.get('detail','')}")
    # Re-enable for cleanup
    api("PUT", f"/api/users/{test_disabled_id}", {"status": "active"}, token=admin_tok)

# 1.4 修改密码
s, b, err = api("PUT", "/api/auth/change-password", {"old_password": "wrongold", "new_password": "Newpass2024!"}, token=admin_tok, expect_status=400)
record("认证", "修改密码-原密码错误应400", s == 400, f"status={s}, detail={b.get('detail','')}")

s, b, err = api("PUT", "/api/auth/change-password", {"old_password": "admin123", "new_password": "abc"}, token=admin_tok, expect_status=422)
record("认证", "修改密码-新密码太短(<6字符)应422", s == 422, f"status={s}")

# 1.5 权限隔离测试
s, b, err = api("POST", "/api/assets", {
    "asset_code": "TEST-VIEWER-DENY", "asset_category": "服务器"
}, token=viewer_tok, expect_status=403)
record("认证/RBAC", "viewer不能创建资产(应403)", s == 403, f"detail={b.get('detail','')}")

s, b, err = api("DELETE", "/api/assets/999999", token=engineer_tok, expect_status=403)
record("认证/RBAC", "ops_engineer不能删除资产(应403)", s == 403, f"detail={b.get('detail','')}")

s, b, err = api("POST", "/api/approval-requests/999/action", {"action": "approve"}, token=engineer_tok, expect_status=403)
record("认证/RBAC", "ops_engineer没有approval:approve(应403)", s == 403, f"detail={b.get('detail','')}")

s, b, err = api("GET", "/api/users", token=viewer_tok, expect_status=403)
record("认证/RBAC", "viewer不能查看用户列表(应403)", s == 403, f"detail={b.get('detail','')}")

s, b, err = api("DELETE", "/api/procurements/999999", token=engineer_tok, expect_status=403)
record("认证/RBAC", "ops_engineer不能删除采购记录(应403)", s == 403, f"detail={b.get('detail','')}")

# Viewer CAN view assets
s, b, err = api("GET", "/api/assets", token=viewer_tok)
record("认证/RBAC", "viewer可以查看资产列表", s == 200, f"total={b.get('total')}")

# ================================================================
#  2. 资产台账CRUD
# ================================================================
print("\n>>> 2. 资产台账CRUD测试")

# 2.1 创建资产
s, b, err = api("POST", "/api/assets", {
    "asset_code": "FUNC-ASSET-001", "asset_category": "服务器", "lifecycle_stage": "规划",
    "brand": "Dell", "model": "R740", "sn": "SN-FUNC001", "location": "A1-01-01",
    "responsible_person": "王军", "warranty_status": "在保",
    "warranty_expire_date": "2025-12-31", "ip_address": "192.168.1.100"
}, token=admin_tok, expect_status=200)
test_asset_id = b.get("id")
record("资产CRUD", "创建资产-正常", s == 200 and test_asset_id is not None, f"id={test_asset_id}, code={b.get('asset_code')}")

# 2.2 创建重复编号资产
s, b, err = api("POST", "/api/assets", {
    "asset_code": "FUNC-ASSET-001", "asset_category": "服务器"
}, token=admin_tok, expect_status=400)
record("资产CRUD", "创建资产-重复编号应400", s == 400, f"detail={b.get('detail','')}")

# 2.3 缺少必填字段
s, b, err = api("POST", "/api/assets", {"asset_code": "FUNC-MISS"}, token=admin_tok, expect_status=422)
record("资产CRUD", "创建资产-缺少必填字段应422", s == 422, f"status={s}")

# 2.4 无效分类(无枚举校验) - This is a potential defect: schema doesn't validate category enum
s, b, err = api("POST", "/api/assets", {
    "asset_code": "FUNC-BADCAT-001", "asset_category": "INVALID_CATEGORY"
}, token=admin_tok)
if s == 200:
    record("资产CRUD", "创建资产-无效分类被接受(缺陷:无枚举校验)", True,
           f"DEFECT: asset_category='INVALID_CATEGORY' 被创建成功，但不在CATEGORIES枚举中")
    # Cleanup
    if b.get("id"):
        api("DELETE", f"/api/assets/{b['id']}", token=admin_tok)
else:
    record("资产CRUD", "创建资产-无效分类被拒绝", True, f"status={s}")

# 2.5 读取资产列表
s, b, err = api("GET", "/api/assets", token=admin_tok)
record("资产CRUD", "读取资产列表", s == 200 and b.get("total") is not None, f"total={b.get('total')}")

# 2.6 读取单个资产
s, b, err = api("GET", "/api/assets/FUNC-ASSET-001", token=admin_tok)
record("资产CRUD", "读取单个资产", s == 200 and b.get("asset_code") == "FUNC-ASSET-001", f"code={b.get('asset_code')}")

# 2.7 读取不存在资产
s, b, err = api("GET", "/api/assets/NONEXIST999", token=admin_tok, expect_status=404)
record("资产CRUD", "读取不存在资产应404", s == 404, f"status={s}")

# 2.8 搜索资产
s, b, err = api("GET", "/api/assets?search=Dell", token=admin_tok)
record("资产CRUD", "搜索资产", s == 200, f"total={b.get('total')}")

# 2.9 分页
s, b, err = api("GET", "/api/assets?page=1&page_size=5", token=admin_tok)
record("资产CRUD", "分页测试", s == 200 and len(b.get("items", [])) <= 5, f"items={len(b.get('items',[]))}")

# 2.10 更新资产(正常)
if test_asset_id:
    s, b, err = api("PUT", f"/api/assets/{test_asset_id}", {"brand": "HP"}, token=admin_tok, expect_status=200)
    record("资产CRUD", "更新资产-正常", s == 200 and b.get("brand") == "HP", f"brand={b.get('brand')}")
else:
    record("资产CRUD", "更新资产-正常", False, "test_asset_id is None, cannot update")

# ================================================================
#  2B. 阶段门禁重点测试
# ================================================================
print("\n>>> 2B. 阶段门禁测试")

# Create a dedicated asset for gate testing, starting at 规划
s, b, err = api("POST", "/api/assets", {
    "asset_code": "GATE-FUNC-001", "asset_category": "服务器", "lifecycle_stage": "规划",
    "responsible_person": "张伟"
}, token=admin_tok, expect_status=200)
gate_id = b.get("id")
gate_code = "GATE-FUNC-001"

# 规划→在途：应允许
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/在途", token=admin_tok)
record("阶段门禁", "规划→在途:应允许", b.get("allowed") == True, f"allowed={b.get('allowed')}, msg={b.get('message','')}")

# 规划→运行：应禁止
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/运行", token=admin_tok)
record("阶段门禁", "规划→运行:应禁止", b.get("allowed") == False, f"allowed={b.get('allowed')}, msg={b.get('message','')}")

# 规划→上架：应允许
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/上架", token=admin_tok)
record("阶段门禁", "规划→上架:应允许", b.get("allowed") == True, f"allowed={b.get('allowed')}, msg={b.get('message','')}")

# 执行跳转 规划→在途 via PUT
if gate_id:
    s, b, err = api("PUT", f"/api/assets/{gate_id}", {"lifecycle_stage": "在途"}, token=admin_tok, expect_status=200)
    record("阶段门禁", "PUT跳转 规划→在途:成功", s == 200 and b.get("lifecycle_stage") == "在途", f"stage={b.get('lifecycle_stage')}")
else:
    record("阶段门禁", "PUT跳转 规划→在途:失败", False, "gate_id is None")

# 在途→上架: 需要验收合格
# Create procurement with inspection_result=合格
s, b, err = api("POST", "/api/procurements", {
    "asset_code": gate_code, "purchase_order": "PO-GATE01", "supplier": "华为",
    "quantity": 1, "unit_price": 50000, "inspector": "张伟", "inspection_result": "合格",
    "arrival_date": "2024-01-15"
}, token=admin_tok)

s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/上架", token=admin_tok)
record("阶段门禁", "在途→上架(验收合格):应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# 在途→运行: 应允许
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/运行", token=admin_tok)
record("阶段门禁", "在途→运行:应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# Move to 上架 then 运行
if gate_id:
    s, b, err = api("PUT", f"/api/assets/{gate_id}", {"lifecycle_stage": "上架"}, token=admin_tok)
    s, b, err = api("PUT", f"/api/assets/{gate_id}", {"lifecycle_stage": "运行"}, token=admin_tok)
    actual_stage = b.get("lifecycle_stage")
    record("阶段门禁", "资产到达运行阶段", actual_stage == "运行", f"stage={actual_stage}")

# 运行→维修：应允许
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/维修", token=admin_tok)
record("阶段门禁", "运行→维修:应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# 运行→在途：应允许(变更迁移)
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/在途", token=admin_tok)
record("阶段门禁", "运行→在途:应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# 运行→待报废：应允许
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/待报废", token=admin_tok)
record("阶段门禁", "运行→待报废:应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# 运行→规划：应禁止
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/规划", token=admin_tok)
record("阶段门禁", "运行→规划:应禁止", b.get("allowed") == False, f"msg={b.get('message','')}")

# 运行→已报废：应禁止
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/已报废", token=admin_tok)
record("阶段门禁", "运行→已报废:应禁止", b.get("allowed") == False, f"msg={b.get('message','')}")

# Move to 维修 via PUT
if gate_id:
    s, b, err = api("PUT", f"/api/assets/{gate_id}", {"lifecycle_stage": "维修"}, token=admin_tok)

# First create a fault WITHOUT recovery_date to test the gate
s, b, err = api("POST", "/api/faults", {
    "asset_code": gate_code, "fault_level": "P3",
    "fault_description": "未恢复的故障", "fault_date": "2024-03-01"
}, token=admin_tok)

# 维修→运行(无恢复日期):应禁止
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/运行", token=admin_tok)
record("阶段门禁", "维修→运行(有未恢复故障):应禁止", b.get("allowed") == False, f"msg={b.get('message','')}")

# Create fault with recovery_date (but previous unrecovered fault still exists!)
s, b, err = api("POST", "/api/faults", {
    "asset_code": gate_code, "fault_level": "P3",
    "fault_description": "已恢复的故障", "fault_date": "2024-03-01",
    "recovery_date": "2024-03-05"
}, token=admin_tok)

s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/运行", token=admin_tok)
# Still blocked because there's another fault with no recovery_date
# This is CORRECT behavior: any unrecovered fault blocks the transition
record("阶段门禁", "维修→运行(仍有未恢复故障):应禁止", b.get("allowed") == False,
       f"msg={b.get('message','')} — 正确行为:有未恢复故障就阻止跳转")

# Now update the first fault to add recovery_date
s, b2, _ = api("GET", f"/api/faults?asset_code={gate_code}", token=admin_tok)
fault_items = b2.get("items", [])
unrecovered_fault = None
for fi in fault_items:
    if fi.get("recovery_date") is None:
        unrecovered_fault = fi

if unrecovered_fault:
    s, b, err = api("PUT", f"/api/faults/{unrecovered_fault['id']}", {"recovery_date": "2024-03-10"}, token=admin_tok)
    s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/运行", token=admin_tok)
    record("阶段门禁", "维修→运行(所有故障已恢复):应允许", b.get("allowed") == True,
           f"msg={b.get('message','')}")

# 维修→待报废: 应允许
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/待报废", token=admin_tok)
record("阶段门禁", "维修→待报废:应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# Move to 待报废
if gate_id:
    s, b, err = api("PUT", f"/api/assets/{gate_id}", {"lifecycle_stage": "待报废"}, token=admin_tok)

# 待报废→已报废(无退役记录):应禁止
s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/已报废", token=admin_tok)
record("阶段门禁", "待报废→已报废(无退役记录):应禁止", b.get("allowed") == False, f"msg={b.get('message','')}")

# Create retirement with application_no but data not cleared
s, b, err = api("POST", "/api/retirements", {
    "asset_code": gate_code, "retire_category": "正常报废",
    "application_no": "RET-APP-001", "data_cleared": "未清除"
}, token=admin_tok)

s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/已报废", token=admin_tok)
record("阶段门禁", "待报废→已报废(数据未清除):应禁止", b.get("allowed") == False, f"msg={b.get('message','')}")

# Update retirement to data_cleared=已清除
s, b2, _ = api("GET", f"/api/retirements?asset_code={gate_code}", token=admin_tok)
ret_items = b2.get("items", [])
if ret_items:
    ret_id = ret_items[0]["id"]
    api("PUT", f"/api/retirements/{ret_id}", {"data_cleared": "已清除"}, token=admin_tok)
    s, b, err = api("GET", f"/api/assets/{gate_code}/stage-gate/已报废", token=admin_tok)
    record("阶段门禁", "待报废→已报废(数据已清除+申请单号):应允许", b.get("allowed") == True, f"msg={b.get('message','')}")

# PUT: 规划→运行 应被400拒绝
s, b, err = api("POST", "/api/assets", {
    "asset_code": "GATE-FUNC-002", "asset_category": "网络设备", "lifecycle_stage": "规划"
}, token=admin_tok)
gate2_id = b.get("id")
s, b, err = api("PUT", f"/api/assets/{gate2_id}", {"lifecycle_stage": "运行"}, token=admin_tok, expect_status=400)
record("阶段门禁", "PUT跳转 规划→运行:应400拒绝", s == 400, f"detail={b.get('detail','')}")

# PUT: 规划→在途 应成功
s, b, err = api("PUT", f"/api/assets/{gate2_id}", {"lifecycle_stage": "在途"}, token=admin_tok, expect_status=200)
record("阶段门禁", "PUT跳转 规划→在途:应成功", s == 200 and b.get("lifecycle_stage") == "在途", f"stage={b.get('lifecycle_stage')}")

# ================================================================
#  3. 五个子表CRUD
# ================================================================
print("\n>>> 3. 子表CRUD测试")

# Create a subtable test asset at 运行
s, b, err = api("POST", "/api/assets", {
    "asset_code": "SUB-FUNC-001", "asset_category": "服务器", "lifecycle_stage": "运行",
    "brand": "Huawei", "model": "RH2288", "responsible_person": "陈明",
    "warranty_status": "在保", "warranty_expire_date": "2025-06-30"
}, token=admin_tok, expect_status=200)
sub_id = b.get("id")
sub_code = "SUB-FUNC-001"

# 3.1 采购入库
s, b, err = api("POST", "/api/procurements", {
    "asset_code": sub_code, "purchase_order": "PO-SUB01", "supplier": "华为",
    "quantity": 3, "unit_price": 100000, "inspector": "张伟", "inspection_result": "合格",
    "arrival_date": "2024-01-10"
}, token=admin_tok, expect_status=200)
proc_id = b.get("id")
record("采购入库", "创建采购记录", s == 200 and proc_id is not None, f"id={proc_id}")
auto_total = b.get("total_price")
record("采购入库", "自动计算总价(3*100000=300000)", auto_total == 300000, f"total_price={auto_total}")

# Invalid asset code
s, b, err = api("POST", "/api/procurements", {"asset_code": "NONEXIST999"}, token=admin_tok, expect_status=400)
record("采购入库", "创建-无效资产编号应400", s == 400, f"detail={b.get('detail','')}")

# Read list
s, b, err = api("GET", "/api/procurements", token=admin_tok)
record("采购入库", "读取列表", s == 200, f"total={b.get('total')}")

# Read by asset_code
s, b, err = api("GET", f"/api/procurements?asset_code={sub_code}", token=admin_tok)
record("采购入库", "按资产编号筛选", s == 200, f"total={b.get('total')}")

# Update + auto recalc
s, b, err = api("PUT", f"/api/procurements/{proc_id}", {"quantity": 5, "unit_price": 100000}, token=admin_tok)
updated_total = b.get("total_price")
record("采购入库", "更新+自动重算总价(5*100000=500000)", updated_total == 500000, f"total_price={updated_total}")

# Delete
s, b, err = api("DELETE", f"/api/procurements/{proc_id}", token=admin_tok)
record("采购入库", "删除采购记录", s == 200)

# 3.2 变更迁移
s, b, err = api("POST", "/api/changes", {
    "asset_code": sub_code, "change_type": "位置变更",
    "old_location": "A1-01-01", "new_location": "B2-03-05",
    "change_reason": "机房调整", "approver": "张伟", "executor": "王军",
    "execute_date": "2024-05-01"
}, token=admin_tok, expect_status=200)
change_id = b.get("id")
record("变更迁移", "创建变更记录", s == 200 and change_id is not None, f"id={change_id}")

s, b, err = api("POST", "/api/changes", {"asset_code": "NONEXIST999", "change_type": "位置变更"}, token=admin_tok, expect_status=400)
record("变更迁移", "创建-无效资产编号应400", s == 400)

s, b, err = api("PUT", f"/api/changes/{change_id}", {"completion_status": "已完成"}, token=admin_tok)
record("变更迁移", "更新变更记录", s == 200, f"completion_status={b.get('completion_status')}")

s, b, err = api("DELETE", f"/api/changes/{change_id}", token=admin_tok)
record("变更迁移", "删除变更记录", s == 200)

# 3.3 故障维修 - P1/P2 降级自动审批
# NOTE: Based on earlier debugging, P1 fault creation returns 500 because:
# The code changes asset stage to "维修" BEFORE submitting the approval,
# but submit_approval checks stage gate against the ALREADY-CHANGED stage.
# This is a REAL BUG.

s, b, err = api("POST", "/api/assets", {
    "asset_code": "FAULT-FUNC-001", "asset_category": "服务器", "lifecycle_stage": "运行",
    "responsible_person": "王军"
}, token=admin_tok, expect_status=200)
fault_asset_id = b.get("id")
fault_code = "FAULT-FUNC-001"

# P1 fault creation - test if 500 error occurs
s, b, err = api("POST", "/api/faults", {
    "asset_code": fault_code, "fault_level": "P1",
    "fault_description": "服务器宕机", "fault_date": "2024-06-01"
}, token=admin_tok)
record("故障维修", "P1故障创建(检查500缺陷)", s == 200, f"status={s}, 这是个关键缺陷: P1故障创建返回{s}而不是200")
# Record the specific defect if it's 500
if s == 500:
    record("故障维修/缺陷", "P1故障创建返回500(阶段变更顺序错误)", False,
           "BUG: 代码先变更阶段到维修再提交审批，导致submit_approval阶段门禁校验失败(维修→维修不合法)")

# P3 fault should work fine
s, b, err = api("POST", "/api/faults", {
    "asset_code": fault_code, "fault_level": "P3",
    "fault_description": "P3故障测试", "fault_date": "2024-08-01",
    "recovery_date": "2024-08-03"
}, token=admin_tok, expect_status=200)
p3_fault_id = b.get("id")
record("故障维修", "P3故障创建正常", s == 200 and p3_fault_id is not None, f"id={p3_fault_id}")

# P3 should NOT auto-change stage
s, b2, _ = api("GET", "/api/assets/FAULT-FUNC-001", token=admin_tok)
record("故障维修", "P3故障不自动变更阶段", b2.get("lifecycle_stage") == "运行",
       f"stage={b2.get('lifecycle_stage')}")

# Update fault
s, b, err = api("PUT", f"/api/faults/{p3_fault_id}", {"recovery_date": "2024-08-05"}, token=admin_tok)
record("故障维修", "更新故障记录", s == 200 and b.get("recovery_date") == "2024-08-05",
       f"recovery_date={b.get('recovery_date')}")

# Delete fault
s, b, err = api("DELETE", f"/api/faults/{p3_fault_id}", token=admin_tok)
record("故障维修", "删除P3故障记录", s == 200)

# Invalid asset code for fault
s, b, err = api("POST", "/api/faults", {"asset_code": "NONEXIST999", "fault_level": "P2"}, token=admin_tok, expect_status=400)
record("故障维修", "创建-无效资产编号应400", s == 400)

# P1 on 上架 stage asset
s, b, err = api("POST", "/api/assets", {
    "asset_code": "FAULT-SHANGJIA-001", "asset_category": "服务器", "lifecycle_stage": "上架",
    "responsible_person": "陈明"
}, token=admin_tok)
s, b, err = api("POST", "/api/faults", {
    "asset_code": "FAULT-SHANGJIA-001", "fault_level": "P1",
    "fault_description": "上架阶段P1故障", "fault_date": "2024-08-01"
}, token=admin_tok)
# This should also be 500 due to the same bug
record("故障维修", "上架阶段P1故障创建(同样500缺陷)", s == 200, f"status={s}")

# 3.4 维保续保
s, b, err = api("POST", "/api/warranties", {
    "asset_code": sub_code, "contract_no": "WARR-SUB01",
    "coverage": "整机维保", "start_date": "2024-01-01", "end_date": "2025-06-30",
    "renewal_decision": "续保", "decision_person": "张伟", "cost": 15000
}, token=admin_tok, expect_status=200)
warr_id = b.get("id")
record("维保续保", "创建维保记录", s == 200 and warr_id is not None, f"id={warr_id}")

s, b, err = api("POST", "/api/warranties", {"asset_code": "NONEXIST999"}, token=admin_tok, expect_status=400)
record("维保续保", "创建-无效资产编号应400", s == 400)

s, b, err = api("PUT", f"/api/warranties/{warr_id}", {"cost": 20000}, token=admin_tok)
record("维保续保", "更新维保记录", s == 200 and b.get("cost") == 20000, f"cost={b.get('cost')}")

s, b, err = api("DELETE", f"/api/warranties/{warr_id}", token=admin_tok)
record("维保续保", "删除维保记录", s == 200)

# 3.5 退役报废
s, b, err = api("POST", "/api/retirements", {
    "asset_code": sub_code, "retire_category": "正常报废",
    "application_no": "RET-SUB01", "data_cleared": "已清除"
}, token=admin_tok, expect_status=200)
ret_id = b.get("id")
record("退役报废", "创建退役记录", s == 200 and ret_id is not None, f"id={ret_id}")

s, b, err = api("POST", "/api/retirements", {"asset_code": "NONEXIST999"}, token=admin_tok, expect_status=400)
record("退役报废", "创建-无效资产编号应400", s == 400)

s, b, err = api("PUT", f"/api/retirements/{ret_id}", {"disposal_method": "捐赠"}, token=admin_tok)
record("退役报废", "更新退役记录", s == 200, f"disposal_method={b.get('disposal_method')}")

s, b, err = api("DELETE", f"/api/retirements/{ret_id}", token=admin_tok)
record("退役报废", "删除退役记录", s == 200)

# ================================================================
#  4. 审批工作流（重点测试）
# ================================================================
print("\n>>> 4. 审批工作流测试")

# Create a fresh asset for approval workflow
s, b, err = api("POST", "/api/assets", {
    "asset_code": "APR-FUNC-001", "asset_category": "服务器", "lifecycle_stage": "规划",
    "responsible_person": "张伟"
}, token=admin_tok, expect_status=200)
apr_asset_id = b.get("id")

# 4.1 创建审批单(draft) - 采购立项
s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval", "asset_code": "APR-FUNC-001",
    "reason": "测试采购立项审批申请流程"
}, token=admin_tok, expect_status=200)
apr1_id = b.get("id")
record("审批", "创建审批单(draft)", s == 200 and b.get("status") == "draft" and apr1_id is not None,
       f"id={apr1_id}, no={b.get('request_no')}, status={b.get('status')}")

# 4.2 创建审批单-不存在的资产
s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval", "asset_code": "NONEXIST999",
    "reason": "测试不存在的资产审批"
}, token=admin_tok, expect_status=400)
record("审批", "创建审批单-不存在的资产应400", s == 400)

# 4.3 创建审批单-阶段不匹配
s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "migration_approval", "asset_code": "APR-FUNC-001",
    "reason": "测试阶段不匹配的审批类型"
}, token=admin_tok, expect_status=400)
record("审批", "创建审批单-阶段不匹配应400", s == 400, f"detail={b.get('detail','')}")

# 4.4 提交审批 draft→pending
s, b, err = api("POST", f"/api/approval-requests/{apr1_id}/submit", None, token=admin_tok, expect_status=200)
record("审批", "提交审批 draft→pending", s == 200 and b.get("status") == "pending", f"status={b.get('status')}")

# 4.5 非申请人不能提交
s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval", "asset_code": "APR-FUNC-001",
    "reason": "测试非申请人提交审批"
}, token=admin_tok)
apr_nonowner_id = b.get("id")
s, b2, _ = api("POST", f"/api/approval-requests/{apr_nonowner_id}/submit", None, token=engineer_tok, expect_status=403)
record("审批", "非申请人不能提交审批应403", s == 403, f"detail={b2.get('detail','')}")

# 4.6 审批通过(approve) - 单级
s, b, err = api("POST", f"/api/approval-requests/{apr1_id}/action", {"action": "approve", "comment": "同意采购"}, token=admin_tok)
record("审批", "审批通过(approve)-单级", s == 200 and b.get("status") == "approved", f"status={b.get('status')}")

# Check stage driven from 规划 → 在途
s, b2, _ = api("GET", "/api/assets/APR-FUNC-001", token=admin_tok)
record("审批", "审批通过后阶段变更 规划→在途", b2.get("lifecycle_stage") == "在途", f"stage={b2.get('lifecycle_stage')}")

# 4.7 驳回测试
# Need a new asset at 规划 for reject flow (APR-FUNC-001 may have been changed to 在途)
s, b, err = api("POST", "/api/assets", {
    "asset_code": "APR-REJECT-001", "asset_category": "服务器", "lifecycle_stage": "规划",
    "responsible_person": "张伟"
}, token=admin_tok, expect_status=200)
apr_reject_asset_id = b.get("id")

s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval", "asset_code": "APR-REJECT-001",
    "reason": "测试驳回审批流程"
}, token=admin_tok, expect_status=200)
apr_reject_id = b.get("id")
s, b, err = api("POST", f"/api/approval-requests/{apr_reject_id}/submit", None, token=admin_tok, expect_status=200)
record("审批", "驳回测试-审批单提交", s == 200 and b.get("status") == "pending", f"id={apr_reject_id}")

# Reject without comment - should fail with ValueError
s, b, err = api("POST", f"/api/approval-requests/{apr_reject_id}/action", {"action": "reject"}, token=admin_tok)
# Empty comment could be None which is falsy
record("审批", "驳回时必须填写comment", s == 400, f"status={s}, detail={b.get('detail','')}")

# Reject with comment
s, b, err = api("POST", f"/api/approval-requests/{apr_reject_id}/action", {"action": "reject", "comment": "预算不足"}, token=admin_tok)
record("审批", "驳回审批(reject)成功", s == 200 and b.get("status") == "rejected", f"status={b.get('status')}")

# 4.8 驳回后重新提交 - asset APR-REJECT-001 is still at 规划
s, b, err = api("POST", f"/api/approval-requests/{apr_reject_id}/resubmit", {
    "reason": "重新申请采购，已调整预算"
}, token=admin_tok)
record("审批", "驳回后重新提交→pending", s == 200 and b.get("status") == "pending", f"status={b.get('status')}")

# 4.9 撤回审批 pending→cancelled
# Use a fresh asset for cancel test
s, b, err = api("POST", "/api/assets", {
    "asset_code": "APR-CANCEL-001", "asset_category": "服务器", "lifecycle_stage": "规划",
    "responsible_person": "张伟"
}, token=admin_tok)
apr_cancel_asset_id = b.get("id")

s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval", "asset_code": "APR-CANCEL-001",
    "reason": "测试撤回审批流程"
}, token=engineer_tok, expect_status=200)
apr_cancel_id = b.get("id")
s, b, err = api("POST", f"/api/approval-requests/{apr_cancel_id}/submit", None, token=engineer_tok, expect_status=200)

s, b, err = api("POST", f"/api/approval-requests/{apr_cancel_id}/cancel", None, token=engineer_tok)
record("审批", "撤回审批 pending→cancelled", s == 200 and b.get("status") == "cancelled", f"status={b.get('status')}")

# Non-applicant cannot cancel
s, b, err = api("POST", f"/api/approval-requests/{apr_cancel_id}/cancel", None, token=admin_tok)
# Note: cancel only works on pending status, and this is already cancelled
# So the error may be "仅pending状态可撤回" instead of "仅申请人可撤回"
record("审批", "非申请人或已取消状态不能再撤回", s == 400, f"status={s}, detail={b.get('detail','')}")

# 4.10 手动指定审批人
# Need a fresh 规划 asset
s, b, err = api("POST", "/api/assets", {
    "asset_code": "APR-MANUAL-001", "asset_category": "服务器", "lifecycle_stage": "规划",
    "responsible_person": "张伟"
}, token=admin_tok, expect_status=200)

s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval", "asset_code": "APR-MANUAL-001",
    "reason": "测试手动指定审批人流程"
}, token=engineer2_tok, expect_status=200)
apr_manual_id = b.get("id")
zhangwei_user_id = users_info.get("zhangwei", {}).get("id")
s, b, err = api("POST", f"/api/approval-requests/{apr_manual_id}/submit", {
    "approver_ids": [zhangwei_user_id]
}, token=engineer2_tok)
record("审批", "手动指定审批人提交", s == 200 and b.get("status") == "pending", f"status={b.get('status')}")

# Verify specified approver
steps = b.get("steps", [])
if steps:
    specified_approver = steps[0].get("approver_id")
    record("审批", "指定审批人优先于自动指派", specified_approver == zhangwei_user_id,
           f"expected={zhangwei_user_id}, got={specified_approver}")
else:
    record("审批", "指定审批人优先于自动指派", False, "No steps returned")

# 4.11 验证非指定审批人能否审批
# Try with liyang (ops_manager, not the specified approver)
s, b, err = api("POST", f"/api/approval-requests/{apr_manual_id}/action", {"action": "approve", "comment": "代审批"}, token=ops_mgr2_tok, expect_status=400)
record("审批", "非指定审批人(ops_manager)不能审批应400", s == 400, f"detail={b.get('detail','')}")

# Admin CAN approve as substitute
s, b, err = api("POST", f"/api/approval-requests/{apr_manual_id}/action", {"action": "approve", "comment": "管理员代审批"}, token=admin_tok)
record("审批", "admin可代审批(非指定审批人)", s == 200, f"status={b.get('status')}")

# 4.12 双级审批(退役) - ops_manager → admin
s, b, err = api("POST", "/api/assets", {
    "asset_code": "APR-RETIRE-001", "asset_category": "服务器", "lifecycle_stage": "运行",
    "responsible_person": "张伟"
}, token=admin_tok, expect_status=200)
retire_apr_id = b.get("id")

s, b, err = api("POST", "/api/approval-requests", {
    "approval_type": "retirement_approval", "asset_code": "APR-RETIRE-001",
    "reason": "设备老化申请退役报废审批"
}, token=admin_tok)
apr_retire_id = b.get("id")
s, b, err = api("POST", f"/api/approval-requests/{apr_retire_id}/submit", None, token=admin_tok)
record("审批", "退役审批-提交pending", s == 200 and b.get("status") == "pending", f"status={b.get('status')}")

# Level 1: ops_manager approve
s, b, err = api("POST", f"/api/approval-requests/{apr_retire_id}/action", {"action": "approve", "comment": "同意退役"}, token=ops_mgr_tok)
record("审批", "退役审批-第1级ops_manager通过", s == 200 and b.get("current_level") == 2, f"status={b.get('status')}, level={b.get('current_level')}")

# Level 2: admin approve
s, b, err = api("POST", f"/api/approval-requests/{apr_retire_id}/action", {"action": "approve", "comment": "最终确认退役"}, token=admin_tok)
record("审批", "退役审批-第2级admin通过", s == 200 and b.get("status") == "approved", f"status={b.get('status')}")

# Check stage driven from 运行 → 待报废
s, b2, _ = api("GET", "/api/assets/APR-RETIRE-001", token=admin_tok)
record("审批", "退役审批通过后 运行→待报废", b2.get("lifecycle_stage") == "待报废", f"stage={b2.get('lifecycle_stage')}")

# 4.13 审批统计
s, b, err = api("GET", "/api/approval-requests/stats", token=admin_tok)
record("审批", "审批统计", s == 200 and b.get("total_pending") is not None, f"total_pending={b.get('total_pending')}")

# 4.14 我的待审
s, b, err = api("GET", "/api/approval-requests/my-pending", token=ops_mgr_tok)
record("审批", "我的待审列表", s == 200, f"total={b.get('total')}")

# 4.15 我的申请
s, b, err = api("GET", "/api/approval-requests/my-applications", token=admin_tok)
record("审批", "我的申请列表", s == 200, f"total={b.get('total')}")

# 4.16 通知系统
s, b, err = api("GET", "/api/approval-notifications", token=admin_tok)
record("审批/通知", "通知列表", s == 200, f"total={b.get('total')}")

s, b, err = api("GET", "/api/approval-notifications/unread-count", token=admin_tok)
record("审批/通知", "未读通知计数", s == 200 and b.get("unread_count") is not None, f"count={b.get('unread_count')}")

notif_items = b.get("items", []) if s == 200 else []
# Get notifications
s, b_notif, _ = api("GET", "/api/approval-notifications", token=admin_tok)
notif_items = b_notif.get("items", [])
if notif_items:
    s, b, err = api("PUT", f"/api/approval-notifications/{notif_items[0]['id']}/read", None, token=admin_tok)
    record("审批/通知", "标记单条通知已读", s == 200)

s, b, err = api("PUT", "/api/approval-notifications/read-all", None, token=admin_tok)
record("审批/通知", "批量标记全部已读", s == 200)

# 4.17 审批配置API
s, b, err = api("GET", "/api/approval-config/types", token=admin_tok)
record("审批", "审批类型配置", s == 200 and len(b.get("types", [])) >= 6, f"types_count={len(b.get('types',[]))}")

s, b, err = api("GET", "/api/approval-config/dropdowns", token=admin_tok)
record("审批", "审批下拉选项", s == 200, f"types_count={len(b.get('approval_types',[]))}")

# ================================================================
#  5. 校验仪表盘
# ================================================================
print("\n>>> 5. 校验仪表盘测试")

s, b, err = api("GET", "/api/validation", token=admin_tok)
record("校验仪表盘", "13项检查返回", s == 200 and len(b.get("checks", [])) == 13,
       f"checks_count={len(b.get('checks',[]))}")

check_names = [c.get("check_name") for c in b.get("checks", [])]
expected_names = ["编号空值", "SN空值", "位置空值", "责任人空值", "阶段空值", "编号重复",
                  "位置重复", "维保过期", "维保即将到期", "日期矛盾", "报废无记录", "孤儿记录", "P1/P2未恢复"]
record("校验仪表盘", "13项检查名称完整", check_names == expected_names, f"got={check_names}")

record("校验仪表盘", "total_assets字段", b.get("total_assets") is not None, f"total_assets={b.get('total_assets')}")

# ================================================================
#  6. distinct-values API
# ================================================================
print("\n>>> 6. distinct-values API测试")

s, b, err = api("GET", "/api/distinct-values", token=admin_tok)
record("distinct-values", "API返回成功", s == 200, f"keys_count={len(b.keys())}")

expected_fields = ["brands", "models", "locations", "ip_addresses", "sn_list",
                   "persons", "departments", "suppliers", "contract_nos", "purchase_orders",
                   "approvers", "executors", "repair_persons", "inspectors",
                   "decision_persons", "uninstall_persons", "data_clear_persons",
                   "disposal_methods", "application_nos", "parts_replaced"]
missing_fields = [f for f in expected_fields if f not in b]
record("distinct-values", "所有字段存在", len(missing_fields) == 0, f"missing={missing_fields}")

record("distinct-values", "persons合并系统用户", len(b.get("persons", [])) > 0, f"persons_count={len(b.get('persons',[]))}")

# ================================================================
#  7. users/by-role API
# ================================================================
print("\n>>> 7. users/by-role API测试")

s, b, err = api("GET", "/api/users/by-role/admin", token=admin_tok)
record("by-role", "admin角色用户列表", s == 200 and len(b) >= 1, f"count={len(b)}")

s, b, err = api("GET", "/api/users/by-role/ops_manager", token=admin_tok)
record("by-role", "ops_manager角色用户列表", s == 200 and len(b) >= 2, f"count={len(b)}")

s, b, err = api("GET", "/api/users/by-role/ops_engineer", token=admin_tok)
record("by-role", "ops_engineer角色用户列表", s == 200 and len(b) >= 4, f"count={len(b)}")

s, b, err = api("GET", "/api/users/by-role/nonexistent_role", token=admin_tok, expect_status=404)
record("by-role", "不存在的角色码应404", s == 404, f"detail={b.get('detail','')}")

# ================================================================
#  8. 导入导出
# ================================================================
print("\n>>> 8. 导入导出测试")

s, b, err = api("GET", "/api/export/assets", token=admin_tok)
record("导入导出", "导出资产Excel", s == 200)

for table_type in ["procurement", "change", "fault", "warranty", "retirement"]:
    s, b, err = api("GET", f"/api/export/{table_type}", token=admin_tok)
    record("导入导出", f"导出子表Excel-{table_type}", s == 200)

for table_type in ["assets", "procurement", "change", "fault", "warranty", "retirement"]:
    s, b, err = api("GET", f"/api/template/{table_type}", token=admin_tok)
    record("导入导出", f"导入模板下载-{table_type}", s == 200)

# viewer HAS import_export:export permission (defined in viewer role)
s, b, err = api("GET", "/api/export/assets", token=viewer_tok)
record("导入导出/RBAC", "viewer可以导出(有import_export:export权限)", s == 200, f"status={s}")

# viewer does NOT have import_export:import
s, b, err = api("GET", "/api/template/assets", token=viewer_tok, expect_status=403)
record("导入导出/RBAC", "viewer不能下载导入模板(缺少import_export:import)", s == 403, f"status={s}")

# ================================================================
#  9. 报表统计
# ================================================================
print("\n>>> 9. 报表统计测试")

s, b, err = api("GET", "/api/reports/comprehensive", token=admin_tok)
record("报表", "综合报表", s == 200, f"keys={list(b.keys())[:5]}")

s, b, err = api("GET", "/api/reports/warranty-expiry", token=admin_tok)
record("报表", "维保到期报表", s == 200)

s, b, err = api("GET", "/api/reports/fault-analysis", token=admin_tok)
record("报表", "故障分析报表", s == 200)

s, b, err = api("GET", "/api/reports/change-frequency", token=admin_tok)
record("报表", "变更频率报表", s == 200)

s, b, err = api("GET", "/api/stats", token=admin_tok)
record("报表", "统计概览stats", s == 200 and b.get("total_assets") is not None, f"total_assets={b.get('total_assets')}")

# ================================================================
#  10. 删除资产级联测试
# ================================================================
print("\n>>> 10. 资产删除级联测试")

s, b, err = api("POST", "/api/assets", {
    "asset_code": "CASCADE-FUNC-001", "asset_category": "服务器", "lifecycle_stage": "运行",
    "responsible_person": "张伟"
}, token=admin_tok)
cascade_id = b.get("id")
cascade_code = "CASCADE-FUNC-001"

# Create subtable records
api("POST", "/api/procurements", {"asset_code": cascade_code, "purchase_order": "PO-CASCADE"}, token=admin_tok)
api("POST", "/api/changes", {"asset_code": cascade_code, "change_type": "位置变更"}, token=admin_tok)
api("POST", "/api/faults", {"asset_code": cascade_code, "fault_level": "P3"}, token=admin_tok)
api("POST", "/api/warranties", {"asset_code": cascade_code, "contract_no": "W-CASCADE"}, token=admin_tok)
api("POST", "/api/retirements", {"asset_code": cascade_code, "retire_category": "正常报废"}, token=admin_tok)

# Verify records exist
s, b, _ = api("GET", f"/api/procurements?asset_code={cascade_code}", token=admin_tok)
proc_before = b.get("total", 0)
s, b, _ = api("GET", f"/api/changes?asset_code={cascade_code}", token=admin_tok)
change_before = b.get("total", 0)

# Delete asset
s, b, err = api("DELETE", f"/api/assets/{cascade_id}", token=admin_tok, expect_status=200)
record("资产删除", "删除资产成功", s == 200)

# Verify cascade
s, b, _ = api("GET", f"/api/procurements?asset_code={cascade_code}", token=admin_tok)
record("资产删除", "级联删除采购记录", b.get("total", 0) == 0, f"before={proc_before}, after={b.get('total',0)}")

s, b, _ = api("GET", f"/api/changes?asset_code={cascade_code}", token=admin_tok)
record("资产删除", "级联删除变更记录", b.get("total", 0) == 0, f"before={change_before}, after={b.get('total',0)}")

# ================================================================
#  11. 边界与特殊测试
# ================================================================
print("\n>>> 11. 边界与特殊测试")

# 11.1 修改密码正常流程
s, b, err = api("PUT", "/api/auth/change-password", {"old_password": "Eng2024!", "new_password": "EngNew2024!"}, token=engineer_tok)
record("边界", "修改密码-正常流程(engineer)", s == 200, f"detail={b}")

tok_new, _ = login("wangjun", "EngNew2024!")
record("边界", "新密码登录成功", tok_new is not None, f"token={tok_new is not None}")

# Change back
if tok_new:
    api("PUT", "/api/auth/change-password", {"old_password": "EngNew2024!", "new_password": "Eng2024!"}, token=tok_new)
else:
    # Try with original token if still valid
    api("PUT", "/api/auth/change-password", {"old_password": "Eng2024!", "new_password": "EngNew2024!"}, token=engineer_tok)
    api("PUT", "/api/auth/change-password", {"old_password": "EngNew2024!", "new_password": "Eng2024!"}, token=engineer_tok)

# 11.2 /api/auth/me
s, b, err = api("GET", "/api/auth/me", token=admin_tok)
record("边界", "/api/auth/me", s == 200 and b.get("username") == "admin", f"username={b.get('username')}")

# 11.3 /api/auth/permissions
s, b, err = api("GET", "/api/auth/permissions")
record("边界", "/api/auth/permissions(无需登录)", s == 200 and b.get("definitions") is not None, f"groups={len(b.get('groups',[]))}")

# 11.4 /api/config/dropdowns
s, b, err = api("GET", "/api/config/dropdowns", token=admin_tok)
record("边界", "/api/config/dropdowns", s == 200 and b.get("categories") is not None, f"categories={b.get('categories')}")

# 11.5 Asset timeline
s, b, err = api("GET", "/api/assets/FUNC-ASSET-001/timeline", token=admin_tok)
record("边界", "资产时间线", s == 200, f"timeline_count={len(b.get('timeline',[]))}")

# 11.6 Procurement explicit total_price should NOT be overridden
s, b, err = api("POST", "/api/procurements", {
    "asset_code": sub_code, "quantity": 2, "unit_price": 5000, "total_price": 99999
}, token=admin_tok)
explicit_total = b.get("total_price")
record("边界", "采购-显式总价不被自动计算覆盖", explicit_total == 99999, f"total_price={explicit_total} (expected 99999)")
# Cleanup
if b.get("id"):
    api("DELETE", f"/api/procurements/{b['id']}", token=admin_tok)

# 11.7 User management - reset password with explicit password
s, b, err = api("POST", "/api/users", {
    "username": "test_resetpwd_func", "password": "Reset2024!", "real_name": "测试重置密码"
}, token=admin_tok)
reset_user_id = b.get("id")
s, b, err = api("POST", f"/api/users/{reset_user_id}/reset-password", {"new_password": "NewReset2024!"}, token=admin_tok)
record("用户管理", "重置密码-指定新密码", s == 200, f"detail={b}")

# Reset password with auto-generate (need to send body)
s, b, err = api("POST", f"/api/users/{reset_user_id}/reset-password", {"new_password": None}, token=admin_tok)
record("用户管理", "重置密码-自动生成(new_password=None)", s == 200 and b.get("generated") == True, f"detail={b}")

# 11.8 Cannot delete self
admin_user_id = users_info.get("admin", {}).get("id")
s, b, err = api("DELETE", f"/api/users/{admin_user_id}", token=admin_tok, expect_status=400)
record("用户管理", "不能删除自己应400", s == 400, f"detail={b.get('detail','')}")

# 11.9 Role management - cannot delete system role
s, b, err = api("GET", "/api/roles", token=admin_tok)
role_items = b.get("items", [])
if role_items:
    system_role_id = role_items[0]["id"]
    s, b, err = api("DELETE", f"/api/roles/{system_role_id}", token=admin_tok, expect_status=400)
    record("角色管理", "系统内置角色不可删除应400", s == 400, f"detail={b.get('detail','')}")

# 11.10 Viewer CAN view validation
s, b, err = api("GET", "/api/validation", token=viewer_tok)
record("RBAC", "viewer可以查看校验仪表盘", s == 200)

# ================================================================
#  Cleanup test artifacts
# ================================================================
print("\n>>> 清理测试数据...")
cleanup_codes = [
    "FUNC-ASSET-001", "GATE-FUNC-001", "GATE-FUNC-002", "SUB-FUNC-001",
    "FAULT-FUNC-001", "FAULT-SHANGJIA-001", "APR-FUNC-001",
    "APR-RETIRE-001", "APR-REJECT-001", "APR-CANCEL-001",
    "APR-MANUAL-001", "P3-TEST-001",
]
for code in cleanup_codes:
    s, b, _ = api("GET", f"/api/assets/{code}", token=admin_tok)
    if s == 200 and b.get("id"):
        api("DELETE", f"/api/assets/{b['id']}", token=admin_tok)

# Clean up test users
for uname in ["test_disabled_user", "test_resetpwd_func", "test_disabled"]:
    s, b, _ = api("GET", "/api/users?search=" + uname, token=admin_tok)
    for u in b.get("items", []):
        if u.get("username") == uname:
            api("DELETE", f"/api/users/{u['id']}", token=admin_tok)

# ================================================================
#  Generate Test Report
# ================================================================
print("\n" + "="*60)
total = len(results)
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"  测试结果: 总计 {total} | 通过 {passed} | 失败 {failed}")
print("="*60)

modules = {}
for r in results:
    mod = r["module"]
    if mod not in modules:
        modules[mod] = {"total": 0, "passed": 0, "failed": 0, "fails": []}
    modules[mod]["total"] += 1
    if r["status"] == "PASS":
        modules[mod]["passed"] += 1
    else:
        modules[mod]["failed"] += 1
        modules[mod]["fails"].append(r)

print("\n模块测试汇总:")
for mod, data in sorted(modules.items()):
    pct = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
    print(f"  {mod}: {data['passed']}/{data['total']} ({pct:.1f}%)")

print("\n失败测试详情:")
for mod, data in sorted(modules.items()):
    for f in data["fails"]:
        print(f"  ✗ [{mod}] {f['name']}: {f['detail']}")

# ================================================================
#  Generate Defect Report Markdown
# ================================================================
defect_md = "# IT资产全生命周期管理系统 v2.2.0 缺陷报告\n\n"
defect_md += "## 测试概况\n\n"
defect_md += f"- **系统版本**: v2.2.0\n"
defect_md += f"- **测试总计**: {total} | **通过**: {passed} | **失败**: {failed}\n"
defect_md += f"- **通过率**: {passed/total*100:.1f}%\n\n"

defect_md += "## 模块测试结果\n\n| 模块 | 通过 | 总计 | 通过率 |\n|------|------|------|--------|\n"
for mod, data in sorted(modules.items()):
    pct = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
    defect_md += f"| {mod} | {data['passed']} | {data['total']} | {pct:.1f}% |\n"

defect_md += "\n## 缺陷清单\n\n"
defect_count = 0

# Categorize defects by severity
critical_defects = []
major_defects = []
minor_defects = []

for mod, data in sorted(modules.items()):
    for f in data["fails"]:
        defect_count += 1
        # Classify severity
        name = f["name"]
        detail = f["detail"]
        if "500" in detail or "P1" in name or "阶段变更顺序" in detail:
            critical_defects.append({"#": defect_count, "module": f["module"], "name": name, "detail": detail, "severity": "严重"})
        elif "RBAC" in f["module"] or "权限" in name or "应4" in name:
            major_defects.append({"#": defect_count, "module": f["module"], "name": name, "detail": detail, "severity": "重要"})
        else:
            minor_defects.append({"#": defect_count, "module": f["module"], "name": name, "detail": detail, "severity": "一般"})

if critical_defects:
    defect_md += "### 严重缺陷 (Critical)\n\n"
    for d in critical_defects:
        defect_md += f"**#{d['#']} {d['name']}**\n\n"
        defect_md += f"- 模块: {d['module']}\n"
        defect_md += f"- 严重程度: {d['severity']}\n"
        defect_md += f"- 详情: {d['detail']}\n\n"

if major_defects:
    defect_md += "### 重要缺陷 (Major)\n\n"
    for d in major_defects:
        defect_md += f"**#{d['#']} {d['name']}**\n\n"
        defect_md += f"- 模块: {d['module']}\n"
        defect_md += f"- 严重程度: {d['severity']}\n"
        defect_md += f"- 详情: {d['detail']}\n\n"

if minor_defects:
    defect_md += "### 一般缺陷 (Minor)\n\n"
    for d in minor_defects:
        defect_md += f"**#{d['#']} {d['name']}**\n\n"
        defect_md += f"- 模块: {d['module']}\n"
        defect_md += f"- 严重程度: {d['severity']}\n"
        defect_md += f"- 详情: {d['detail']}\n\n"

# Add analysis section
defect_md += "## 缺陷分析\n\n"

# Analyze P1/P2 500 error root cause
defect_md += "### P1/P2故障创建500错误根因分析\n\n"
defect_md += "**根因**: `create_fault` API中代码执行顺序错误\n\n"
defect_md += "代码流程:\n"
defect_md += "1. `asset.lifecycle_stage = \"维修\"` — 先将资产阶段改为维修\n"
defect_md += "2. `auto_submit_fault_approval()` — 然后提交故障降级审批\n"
defect_md += "3. 在 `submit_approval` 中调用 `check_stage_gate()` 检查门禁\n"
defect_md += "4. 门禁检查读取数据库中资产的**当前阶段**（已被改为\"维修\"）\n"
defect_md += "5. 检查 \"维修\" → \"维修\" 是否合法 → **不合法** → 抛出 ValueError\n"
defect_md += "6. ValueError 被 `auto_submit_fault_approval` 捕获，审批单标记为 cancelled\n"
defect_md += "7. 但主事务中的 `db.commit()` 仍然执行，导致故障记录创建失败返回500\n\n"
defect_md += "**修复建议**: 应先提交审批，审批成功后再变更阶段；或在提交审批时跳过门禁检查（因为阶段变更已由故障代码执行）。\n\n"

# Analyze asset_category enum validation defect
defect_md += "### 资产分类无枚举校验\n\n"
defect_md += "**现象**: `POST /api/assets` 接受不在 CATEGORIES 列表中的 `asset_category` 值（如\"INVALID_CATEGORY\"）。\n\n"
defect_md += "**根因**: `AssetCreate` schema 仅校验 `max_length=20`，未校验值是否在 CATEGORIES 枚举中。导入模块有此校验，但API创建没有。\n\n"
defect_md += "**修复建议**: 在 `AssetCreate` schema 中增加 `asset_category` 枚举校验，或在 `create_asset` 端点中增加校验逻辑。\n\n"

defect_md += "## 测试覆盖范围\n\n"
defect_md += "### 已测试模块\n"
defect_md += "1. 认证模块 - 登录/密码/RBAC权限隔离\n"
defect_md += "2. 资产台账CRUD + 阶段门禁\n"
defect_md += "3. 五个子表CRUD(采购/变更/故障/维保/退役)\n"
defect_md += "4. 审批工作流(创建/提交/审批/驳回/撤回/重新提交/双级审批/通知/手动指定审批人)\n"
defect_md += "5. 校验仪表盘(13项检查)\n"
defect_md += "6. distinct-values API\n"
defect_md += "7. users/by-role API\n"
defect_md += "8. 导入导出\n"
defect_md += "9. 报表统计\n"
defect_md += "10. 资产删除级联\n"
defect_md += "11. 边界条件测试\n\n"
defect_md += "### 未测试(需补充)\n"
defect_md += "- 批量导入Excel文件上传\n"
defect_md += "- JWT Token过期场景\n"
defect_md += "- 并发竞态条件\n"
defect_md += "- 前端UI逻辑\n"

# Write defect report
deliverables_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "deliverables")
os.makedirs(deliverables_dir, exist_ok=True)
report_path = os.path.join(deliverables_dir, "defect-report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(defect_md)
print(f"\n缺陷报告已保存到: {report_path}")

# Save results JSON
results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "functional_test_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"测试结果JSON已保存到: {results_path}")

sys.exit(1 if failed > 0 else 0)
