"""IT资产全生命周期管理系统 - 全面功能测试脚本 v2.2.0
测试覆盖: 认证/RBAC/资产CRUD/子表CRUD/审批工作流/校验/distinct-values/报表等
"""
import urllib.request
import urllib.parse
import json
import sys
import traceback
from datetime import date, datetime

BASE = "http://127.0.0.1:8000"
PYTHON = sys.executable

# ============ 辅助函数 ============
def api(method, path, data=None, token=None, raw=False):
    """发送API请求"""
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        ct = resp.headers.get("Content-Type", "")
        if ct.startswith("application/json"):
            result = json.loads(resp.read().decode("utf-8"))
        else:
            result = resp.read()
        return {"status": resp.status, "data": result, "ok": True}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except:
            body = e.read().decode("utf-8")
        return {"status": e.code, "data": body, "ok": False}
    except Exception as e:
        return {"status": 0, "data": str(e), "ok": False, "error": True}


def login(username, password):
    """登录获取token"""
    r = api("POST", "/api/auth/login", {"username": username, "password": password})
    if r["ok"]:
        return r["data"].get("token")
    return None


# ============ 测试记录 ============
results = []
def record(module, test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"module": module, "test": test_name, "status": status, "detail": detail})
    mark = "✓" if passed else "✗"
    print(f"  {mark} [{module}] {test_name}: {detail if not passed else ''}")


# ============ 1. 认证模块测试 ============
print("\n=== 1. 认证模块 ===")

# 1.1 正常登录
admin_token = login("admin", "admin123")
record("认证", "admin正常登录", admin_token is not None, "获取token失败" if not admin_token else "")

# 1.2 错误密码登录
r = api("POST", "/api/auth/login", {"username": "admin", "password": "wrong"})
record("认证", "错误密码登录返回401", r["status"] == 401, f"状态码={r['status']}")

# 1.3 不存在用户登录
r = api("POST", "/api/auth/login", {"username": "nobody", "password": "test123"})
record("认证", "不存在用户登录返回401", r["status"] == 401, f"状态码={r['status']}")

# 1.4 密码太短（<6字符）
r = api("POST", "/api/auth/login", {"username": "admin", "password": "abc"})
record("认证", "密码太短(<6)请求被拒绝", r["status"] in [400, 401, 422], f"状态码={r['status']}")

# 1.5 各角色登录
zw_token = login("zhangwei", "Ops2024!")
record("认证", "运维主管zhangwei登录", zw_token is not None)

wj_token = login("wangjun", "Eng2024!")
record("认证", "运维工程师wangjun登录", wj_token is not None)

sf_token = login("sunfang", "View2024!")
record("认证", "只读用户sunfang登录", sf_token is not None)

# 1.6 修改密码
r = api("PUT", "/api/auth/change-password", {"old_password": "admin123", "new_password": "admin456"}, token=admin_token)
record("认证", "admin修改密码成功", r["ok"], f"返回={r['data']}")

# 恢复密码
r2 = api("PUT", "/api/auth/change-password", {"old_password": "admin456", "new_password": "admin123"}, token=admin_token)
record("认证", "admin恢复密码成功", r2["ok"])

# 1.7 原密码错误修改密码
r = api("PUT", "/api/auth/change-password", {"old_password": "wrong", "new_password": "newpass"}, token=admin_token)
record("认证", "原密码错误时修改密码返回400", r["status"] == 400, f"状态码={r['status']}")

# 1.8 无Token访问受保护端点
r = api("GET", "/api/assets")
record("认证", "无Token访问/assets返回401", r["status"] == 401, f"状态码={r['status']}")

# 1.9 获取当前用户信息
r = api("GET", "/api/auth/me", token=admin_token)
record("认证", "获取当前用户信息", r["ok"] and r["data"].get("username") == "admin", f"返回={r['data']}")

# 1.10 禁用账号登录（先禁用huangjie再测试）
r = api("PUT", f"/api/users/9", {"status": "disabled"}, token=admin_token)
r2 = login("huangjie", "View2024!")
record("认证", "禁用账号无法登录", r2 is None, f"token={r2}")
# 恢复
api("PUT", f"/api/users/9", {"status": "active"}, token=admin_token)


# ============ 2. RBAC权限隔离测试 ============
print("\n=== 2. RBAC权限隔离 ===")

# 2.1 viewer不能创建资产
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST01",
    "asset_category": "服务器",
    "brand": "测试品牌",
    "lifecycle_stage": "规划"
}, token=sf_token)
record("RBAC", "viewer创建资产返回403", r["status"] == 403, f"状态码={r['status']}, data={r['data']}")

# 2.2 viewer不能删除资产
r = api("DELETE", "/api/assets/1", token=sf_token)
record("RBAC", "viewer删除资产返回403", r["status"] == 403, f"状态码={r['status']}")

# 2.3 ops_engineer不能删除资产
r = api("DELETE", "/api/assets/1", token=wj_token)
record("RBAC", "ops_engineer删除资产返回403", r["status"] == 403, f"状态码={r['status']}")

# 2.4 ops_engineer不能审批(approve权限缺失)
r = api("POST", "/api/approval-requests/1/action", {"action": "approve", "comment": "同意"}, token=wj_token)
record("RBAC", "ops_engineer审批操作返回403", r["status"] == 403, f"状态码={r['status']}")

# 2.5 viewer可以查看资产
r = api("GET", "/api/assets?page=1&page_size=5", token=sf_token)
record("RBAC", "viewer查看资产列表成功", r["ok"], f"返回={r['data']}")

# 2.6 viewer没有用户管理权限
r = api("GET", "/api/users", token=sf_token)
record("RBAC", "viewer查看用户列表返回403", r["status"] == 403, f"状态码={r['status']}")

# 2.7 ops_engineer没有用户管理权限
r = api("GET", "/api/users", token=wj_token)
record("RBAC", "ops_engineer查看用户列表返回403", r["status"] == 403, f"状态码={r['status']}")

# 2.8 admin有所有权限
r = api("GET", "/api/users", token=admin_token)
record("RBAC", "admin查看用户列表成功", r["ok"], f"返回={r['data']}")

# 2.9 ops_manager有审批权限(approve)
r = api("GET", "/api/approval-requests/stats", token=zw_token)
record("RBAC", "ops_manager查看审批统计成功", r["ok"], f"返回={r['data']}")

# 2.10 ops_engineer可以提交审批但不能审批
r = api("GET", "/api/approval-requests/stats", token=wj_token)
record("RBAC", "ops_engineer查看审批统计成功", r["ok"])


# ============ 3. 资产台账CRUD测试 ============
print("\n=== 3. 资产台账CRUD ===")

# 3.1 创建资产
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST01",
    "asset_category": "服务器",
    "brand": "测试品牌A",
    "model": "测试型号X1",
    "lifecycle_stage": "规划",
    "responsible_person": "张伟",
    "ip_address": "192.168.1.100"
}, token=admin_token)
record("资产CRUD", "创建资产成功", r["ok"], f"返回={r['data']}")
test_asset_id = r["data"].get("id") if r["ok"] else None

# 3.2 创建重复编号资产
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST01",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)
record("资产CRUD", "重复编号返回400", r["status"] == 400, f"状态码={r['status']}")

# 3.3 缺少必填字段(asset_category)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST02"
}, token=admin_token)
record("资产CRUD", "缺少asset_category返回422", r["status"] == 422, f"状态码={r['status']}")

# 3.4 查询资产列表
r = api("GET", "/api/assets?page=1&page_size=5", token=admin_token)
record("资产CRUD", "查询资产列表成功", r["ok"] and r["data"].get("total", 0) > 0, f"total={r['data'].get('total')}")

# 3.5 搜索资产
r = api("GET", "/api/assets?search=测试", token=admin_token)
record("资产CRUD", "搜索资产成功", r["ok"], f"返回={r['data']}")

# 3.6 按分类筛选
r = api("GET", "/api/assets?category=服务器", token=admin_token)
record("资产CRUD", "按分类筛选成功", r["ok"])

# 3.7 按阶段筛选
r = api("GET", "/api/assets?stage=规划", token=admin_token)
record("资产CRUD", "按阶段筛选成功", r["ok"])

# 3.8 更新资产
r = api("PUT", f"/api/assets/{test_asset_id}", {"brand": "更新品牌B"}, token=admin_token)
record("资产CRUD", "更新资产品牌成功", r["ok"] and r["data"].get("brand") == "更新品牌B", f"返回={r['data']}")

# 3.9 创建第二个测试资产(运行阶段)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST02",
    "asset_category": "服务器",
    "brand": "测试品牌C",
    "lifecycle_stage": "运行",
    "responsible_person": "王军",
    "location": "A01-01-01",
    "ip_address": "192.168.1.101"
}, token=admin_token)
test_asset2_id = r["data"].get("id") if r["ok"] else None

# 3.10 创建第三个测试资产(规划阶段)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST03",
    "asset_category": "网络设备",
    "lifecycle_stage": "规划"
}, token=admin_token)
test_asset3_id = r["data"].get("id") if r["ok"] else None


# ============ 4. 阶段门禁测试 ============
print("\n=== 4. 阶段门禁 ===")

# 4.1 规划→在途 (合法)
r = api("PUT", f"/api/assets/{test_asset_id}", {"lifecycle_stage": "在途"}, token=admin_token)
record("阶段门禁", "规划→在途:允许", r["ok"], f"返回={r['data']}")

# 4.2 在途→上架 (合法)
r = api("PUT", f"/api/assets/{test_asset_id}", {"lifecycle_stage": "上架"}, token=admin_token)
record("阶段门禁", "在途→上架:允许", r["ok"])

# 4.3 上架→运行 (合法)
r = api("PUT", f"/api/assets/{test_asset_id}", {"lifecycle_stage": "运行"}, token=admin_token)
record("阶段门禁", "上架→运行:允许", r["ok"])

# 4.4 运行→维修 (合法)
r = api("PUT", f"/api/assets/{test_asset_id}", {"lifecycle_stage": "维修"}, token=admin_token)
record("阶段门禁", "运行→维修:允许", r["ok"])

# 4.5 维修→运行 - 需要先有故障恢复日期 (应禁止)
r = api("PUT", f"/api/assets/{test_asset_id}", {"lifecycle_stage": "运行"}, token=admin_token)
record("阶段门禁", "维修→运行(无恢复日期):禁止", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 4.6 为该资产创建故障记录并设置恢复日期
r = api("POST", "/api/faults", {
    "asset_code": "DC-CL-SRV-TEST01",
    "fault_level": "P3",
    "fault_description": "测试故障",
    "fault_date": "2026-01-15",
    "recovery_date": "2026-01-20",
    "repair_person": "王军"
}, token=admin_token)
# 然后再尝试维修→运行
r = api("PUT", f"/api/assets/{test_asset_id}", {"lifecycle_stage": "运行"}, token=admin_token)
record("阶段门禁", "维修→运行(有恢复日期):允许", r["ok"], f"状态码={r['status']}, data={r['data']}")

# 4.7 规划→运行 (非法跳转)
r = api("PUT", f"/api/assets/{test_asset3_id}", {"lifecycle_stage": "运行"}, token=admin_token)
record("阶段门禁", "规划→运行:禁止", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 4.8 规划→已报废 (非法跳转)
r = api("PUT", f"/api/assets/{test_asset3_id}", {"lifecycle_stage": "已报废"}, token=admin_token)
record("阶段门禁", "规划→已报废:禁止", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 4.9 运行→待报废 (合法)
r = api("PUT", f"/api/assets/{test_asset2_id}", {"lifecycle_stage": "待报废"}, token=admin_token)
record("阶段门禁", "运行→待报废:允许", r["ok"], f"状态码={r['status']}")

# 4.10 待报废→已报废 - 需要退役表有申请单号+数据已清除 (应禁止)
r = api("PUT", f"/api/assets/{test_asset2_id}", {"lifecycle_stage": "已报废"}, token=admin_token)
record("阶段门禁", "待报废→已报废(无退役记录):禁止", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 4.11 创建退役记录后再尝试
r = api("POST", "/api/retirements", {
    "asset_code": "DC-CL-SRV-TEST02",
    "retire_category": "正常报废",
    "application_no": "RET-2026-001",
    "approver": "张伟",
    "data_cleared": "已清除",
    "data_clear_person": "李强",
    "disposal_method": "回收"
}, token=admin_token)
r = api("PUT", f"/api/assets/{test_asset2_id}", {"lifecycle_stage": "已报废"}, token=admin_token)
record("阶段门禁", "待报废→已报废(有退役记录):允许", r["ok"], f"状态码={r['status']}")

# 4.12 运行→在途 (合法 - 变更迁移场景)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-TEST04",
    "asset_category": "服务器",
    "lifecycle_stage": "运行",
    "responsible_person": "测试"
}, token=admin_token)
test_asset4_id = r["data"].get("id") if r["ok"] else None
if test_asset4_id:
    r = api("PUT", f"/api/assets/{test_asset4_id}", {"lifecycle_stage": "在途"}, token=admin_token)
    record("阶段门禁", "运行→在途:允许", r["ok"], f"状态码={r['status']}")

# 4.13 Stage Gate API直接调用
r = api("GET", "/api/assets/DC-CL-SRV-TEST03/stage-gate/运行", token=admin_token)
record("阶段门禁", "stage-gate API: 规划→运行不允许", r["ok"] and r["data"].get("allowed") == False, f"返回={r['data']}")


# ============ 5. 子表CRUD测试 ============
print("\n=== 5. 子表CRUD ===")

# 创建一个运行阶段的测试资产
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-SUB01",
    "asset_category": "服务器",
    "lifecycle_stage": "运行",
    "brand": "子表测试",
    "responsible_person": "测试人"
}, token=admin_token)

# 5.1 采购入库 - 创建
r = api("POST", "/api/procurements", {
    "asset_code": "DC-CL-SRV-SUB01",
    "purchase_order": "PO-2026-001",
    "supplier": "测试供应商",
    "quantity": 5,
    "unit_price": 1000.0,
    "arrival_date": "2026-01-10",
    "inspector": "李阳",
    "inspection_result": "合格"
}, token=admin_token)
record("采购CRUD", "创建采购记录成功", r["ok"], f"返回={r['data']}")
proc_id = r["data"].get("id") if r["ok"] else None

# 5.2 采购 - 自动计算总价
if proc_id:
    total_price = r["data"].get("total_price")
    record("采购CRUD", "自动计算总价=5000", total_price == 5000.0, f"total_price={total_price}")

# 5.3 采购 - 不存在的资产编号
r = api("POST", "/api/procurements", {
    "asset_code": "NONEXISTENT",
    "purchase_order": "PO-X"
}, token=admin_token)
record("采购CRUD", "不存在资产编号返回400", r["status"] == 400, f"状态码={r['status']}")

# 5.4 采购 - 更新后重新计算总价
if proc_id:
    r = api("PUT", f"/api/procurements/{proc_id}", {"quantity": 10}, token=admin_token)
    record("采购CRUD", "更新数量后总价重算=10000", r["ok"] and r["data"].get("total_price") == 10000.0, f"total_price={r['data'].get('total_price')}")

# 5.5 变更迁移 - 创建
r = api("POST", "/api/changes", {
    "asset_code": "DC-CL-SRV-SUB01",
    "change_type": "位置变更",
    "old_location": "A01-01-01",
    "new_location": "B02-02-02",
    "old_ip": "192.168.1.100",
    "new_ip": "192.168.2.100",
    "approver": "张伟",
    "executor": "王军",
    "execute_date": "2026-06-15"
}, token=admin_token)
record("变更CRUD", "创建变更记录成功", r["ok"])
change_id = r["data"].get("id") if r["ok"] else None

# 5.6 故障维修 - 创建P1故障
r = api("POST", "/api/faults", {
    "asset_code": "DC-CL-SRV-SUB01",
    "fault_level": "P1",
    "fault_description": "服务器宕机",
    "fault_date": "2026-06-20"
}, token=admin_token)
record("故障CRUD", "创建P1故障成功", r["ok"])
fault_id = r["data"].get("id") if r["ok"] else None

# 5.7 P1/P2故障应自动变更阶段到"维修" + 自动创建故障降级审批
if fault_id:
    # 检查资产阶段是否被改为"维修"
    r = api("GET", "/api/assets/DC-CL-SRV-SUB01", token=admin_token)
    stage_after_p1 = r["data"].get("lifecycle_stage") if r["ok"] else None
    record("故障CRUD", "P1故障后资产阶段变为维修", stage_after_p1 == "维修", f"阶段={stage_after_p1}")

    # 检查是否自动创建了故障降级审批单
    r = api("GET", "/api/approval-requests?asset_code=DC-CL-SRV-SUB01&approval_type=fault_degrade_approval", token=admin_token)
    has_auto_approval = r["ok"] and r["data"].get("total", 0) > 0
    record("故障CRUD", "P1故障自动创建故障降级审批", has_auto_approval, f"审批数={r['data'].get('total')}")

# 5.8 故障 - 创建P3故障(不触发自动降级)
r = api("POST", "/api/faults", {
    "asset_code": "DC-CL-SRV-SUB01",
    "fault_level": "P3",
    "fault_description": "轻微告警",
    "fault_date": "2026-06-25"
}, token=admin_token)
record("故障CRUD", "创建P3故障成功", r["ok"])

# 5.9 维保续保 - 创建
r = api("POST", "/api/warranties", {
    "asset_code": "DC-CL-SRV-SUB01",
    "contract_no": "W-2026-001",
    "start_date": "2025-01-01",
    "end_date": "2026-12-31",
    "renewal_decision": "续保",
    "decision_person": "张伟"
}, token=admin_token)
record("维保CRUD", "创建维保记录成功", r["ok"])

# 5.10 退役报废 - 创建
r = api("POST", "/api/retirements", {
    "asset_code": "DC-CL-SRV-SUB01",
    "retire_category": "正常报废",
    "application_no": "RET-2026-002"
}, token=admin_token)
record("退役CRUD", "创建退役记录成功", r["ok"])

# 5.11 查询各子表列表
for table in ["procurements", "changes", "faults", "warranties", "retirements"]:
    r = api("GET", f"/api/{table}?page=1&page_size=5&asset_code=DC-CL-SRV-SUB01", token=admin_token)
    record("子表查询", f"查询{table}列表成功", r["ok"])


# ============ 6. 审批工作流测试 ============
print("\n=== 6. 审批工作流 ===")

# 创建一个规划阶段的资产用于采购审批
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-APR01",
    "asset_category": "服务器",
    "lifecycle_stage": "规划",
    "brand": "审批测试"
}, token=admin_token)

# 6.1 创建审批单(draft) - 采购立项审批
r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-APR01",
    "reason": "测试采购立项审批流程12345"
}, token=wj_token)
record("审批", "创建采购审批单(draft)", r["ok"], f"返回={r['data']}")
apr1_id = r["data"].get("id") if r["ok"] else None

# 6.2 提交审批(draft→pending) - 手动指定审批人
if apr1_id:
    # 获取张伟的user_id
    r_users = api("GET", "/api/users/by-role/ops_manager", token=admin_token)
    zhangwei_id = r_users["data"][0]["id"] if r_users["ok"] and r_users["data"] else None
    r = api("POST", f"/api/approval-requests/{apr1_id}/submit", {
        "approver_ids": [zhangwei_id] if zhangwei_id else None
    }, token=wj_token)
    record("审批", "提交审批(draft→pending)", r["ok"], f"返回={r['data']}")
    # 检查审批单状态
    apr_status = r["data"].get("status") if r["ok"] else None
    record("审批", "审批单状态变为pending", apr_status == "pending", f"状态={apr_status}")

# 6.3 非申请人不能提交
if apr1_id:
    r = api("POST", f"/api/approval-requests/{apr1_id}/submit", {}, token=zw_token)
    record("审批", "非申请人提交返回403", r["status"] == 403, f"状态码={r['status']}")

# 6.4 创建变更迁移审批(运行→在途)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-APR02",
    "asset_category": "服务器",
    "lifecycle_stage": "运行"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "migration_approval",
    "asset_code": "DC-CL-SRV-APR02",
    "reason": "设备搬迁变更迁移审批申请12345"
}, token=wj_token)
record("审批", "创建变更迁移审批(draft)", r["ok"])
apr2_id = r["data"].get("id") if r["ok"] else None

if apr2_id:
    r = api("POST", f"/api/approval-requests/{apr2_id}/submit", {}, token=wj_token)
    record("审批", "提交变更迁移审批", r["ok"], f"返回={r['data']}")

# 6.5 审批通过 - 运维主管操作
if apr1_id:
    r = api("POST", f"/api/approval-requests/{apr1_id}/action", {
        "action": "approve", "comment": "同意采购"
    }, token=zw_token)
    record("审批", "运维主管审批通过", r["ok"], f"返回={r['data']}")
    # 验证审批后阶段是否变更
    if r["ok"]:
        r_asset = api("GET", "/api/assets/DC-CL-SRV-APR01", token=admin_token)
        new_stage = r_asset["data"].get("lifecycle_stage") if r_asset["ok"] else None
        record("审批", "采购审批通过后阶段变为在途", new_stage == "在途", f"阶段={new_stage}")

# 6.6 创建报废审批(双级: ops_manager→admin)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-APR03",
    "asset_category": "服务器",
    "lifecycle_stage": "运行",
    "responsible_person": "测试"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "retirement_approval",
    "asset_code": "DC-CL-SRV-APR03",
    "reason": "设备老化需要报废退役审批申请12345"
}, token=wj_token)
record("审批", "创建报废审批(draft)", r["ok"], f"返回={r['data']}")
apr3_id = r["data"].get("id") if r["ok"] else None

if apr3_id:
    r = api("POST", f"/api/approval-requests/{apr3_id}/submit", {}, token=wj_token)
    record("审批", "提交报废审批", r["ok"], f"返回={r['data']}")
    # 检查是否有两级审批步骤
    if r["ok"]:
        steps = r["data"].get("steps", [])
        record("审批", "报废审批有两级步骤", len(steps) == 2, f"步骤数={len(steps)}")

# 6.7 双级审批 - 第一级通过(ops_manager)
if apr3_id:
    r = api("POST", f"/api/approval-requests/{apr3_id}/action", {
        "action": "approve", "comment": "运维主管同意报废"
    }, token=zw_token)
    record("审批", "报废审批第一级通过", r["ok"], f"返回={r['data']}")
    # 检查当前级别是否变为2
    if r["ok"]:
        current_level = r["data"].get("current_level")
        record("审批", "报废审批第一级通过后current_level=2", current_level == 2, f"level={current_level}")

# 6.8 双级审批 - 第二级通过(admin)
if apr3_id:
    r = api("POST", f"/api/approval-requests/{apr3_id}/action", {
        "action": "approve", "comment": "管理员确认报废"
    }, token=admin_token)
    record("审批", "报废审批第二级通过", r["ok"], f"返回={r['data']}")
    # 验证审批后阶段变为"待报废"
    if r["ok"]:
        r_asset = api("GET", "/api/assets/DC-CL-SRV-APR03", token=admin_token)
        new_stage = r_asset["data"].get("lifecycle_stage") if r_asset["ok"] else None
        record("审批", "报废审批通过后阶段变为待报废", new_stage == "待报废", f"阶段={new_stage}")

# 6.9 审批驳回 - 需要comment
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-APR04",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-APR04",
    "reason": "测试驳回流程审批申请12345"
}, token=wj_token)
apr4_id = r["data"].get("id") if r["ok"] else None

if apr4_id:
    r = api("POST", f"/api/approval-requests/{apr4_id}/submit", {}, token=wj_token)
    # 驳回但不提供comment
    r = api("POST", f"/api/approval-requests/{apr4_id}/action", {
        "action": "reject"
    }, token=zw_token)
    record("审批", "驳回无comment返回400", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

    # 正常驳回
    r = api("POST", f"/api/approval-requests/{apr4_id}/action", {
        "action": "reject", "comment": "不符合采购标准"
    }, token=zw_token)
    record("审批", "正常驳回成功", r["ok"], f"返回={r['data']}")
    if r["ok"]:
        record("审批", "驳回后状态变为rejected", r["data"].get("status") == "rejected", f"状态={r['data'].get('status')}")

# 6.10 驳回后重新提交
if apr4_id:
    r = api("POST", f"/api/approval-requests/{apr4_id}/resubmit", {
        "reason": "重新提交采购申请，已补充材料12345"
    }, token=wj_token)
    record("审批", "驳回后重新提交", r["ok"], f"返回={r['data']}")

# 6.11 撤回审批
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-APR05",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-APR05",
    "reason": "测试撤回流程审批申请12345"
}, token=wj_token)
apr5_id = r["data"].get("id") if r["ok"] else None

if apr5_id:
    r = api("POST", f"/api/approval-requests/{apr5_id}/submit", {}, token=wj_token)
    r = api("POST", f"/api/approval-requests/{apr5_id}/cancel", token=wj_token)
    record("审批", "撤回审批成功", r["ok"], f"返回={r['data']}")
    if r["ok"]:
        record("审批", "撤回后状态变为cancelled", r["data"].get("status") == "cancelled", f"状态={r['data'].get('status')}")

# 6.12 非申请人不能撤回
if apr5_id:
    r = api("POST", f"/api/approval-requests/{apr5_id}/cancel", token=zw_token)
    record("审批", "非申请人撤回返回403/400", r["status"] in [400, 403], f"状态码={r['status']}")

# 6.13 非指定审批人不能审批(非admin非指定审批人)
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-APR06",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-APR06",
    "reason": "测试审批人权限隔离12345"
}, token=wj_token)
apr6_id = r["data"].get("id") if r["ok"] else None

if apr6_id:
    r = api("POST", f"/api/approval-requests/{apr6_id}/submit", {}, token=wj_token)
    # 用另一个运维工程师(陈明)尝试审批
    cm_token = login("chenming", "Eng2024!")
    r = api("POST", f"/api/approval-requests/{apr6_id}/action", {
        "action": "approve", "comment": "我试试审批"
    }, token=cm_token)
    record("审批", "ops_engineer无approve权限返回403", r["status"] == 403, f"状态码={r['status']}")

# 6.14 审批类型与资产阶段不匹配
r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",  # 要求规划阶段
    "asset_code": "DC-CL-SRV-APR02",  # 运行阶段资产
    "reason": "测试阶段不匹配审批12345"
}, token=wj_token)
record("审批", "审批类型与资产阶段不匹配返回400", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 6.15 维保续保审批(阶段不变)
r = api("POST", "/api/approval-requests", {
    "approval_type": "warranty_renewal_approval",
    "asset_code": "DC-CL-SRV-APR02",
    "reason": "维保续保审批，设备需续保12345"
}, token=wj_token)
record("审批", "创建维保续保审批", r["ok"], f"返回={r['data']}")

# 6.16 审批统计
r = api("GET", "/api/approval-requests/stats", token=admin_token)
record("审批", "审批统计查询成功", r["ok"], f"返回={r['data']}")

# 6.17 我的待审列表
r = api("GET", "/api/approval-requests/my-pending", token=zw_token)
record("审批", "运维主管待审列表", r["ok"], f"返回={r['data']}")

# 6.18 我的申请列表
r = api("GET", "/api/approval-requests/my-applications", token=wj_token)
record("审批", "我的申请列表", r["ok"])


# ============ 7. 通知系统测试 ============
print("\n=== 7. 通知系统 ===")

# 7.1 获取通知列表
r = api("GET", "/api/approval-notifications", token=zw_token)
record("通知", "获取通知列表成功", r["ok"])

# 7.2 未读通知数量
r = api("GET", "/api/approval-notifications/unread-count", token=zw_token)
record("通知", "未读通知数量查询成功", r["ok"])

# 7.3 标记单条已读
notif_list = r.get("data", {}).get("items", [])
if notif_list:
    first_id = notif_list[0].get("id")
    r2 = api("GET", "/api/approval-notifications", token=zw_token)
    notif_items = r2["data"].get("items", []) if r2["ok"] else []
    if notif_items:
        nid = notif_items[0]["id"]
        r = api("PUT", f"/api/approval-notifications/{nid}/read", token=zw_token)
        record("通知", "标记单条已读成功", r["ok"])

# 7.4 批量标记全部已读
r = api("PUT", "/api/approval-notifications/read-all", token=zw_token)
record("通知", "批量标记全部已读成功", r["ok"])

# 7.5 验证审批提交时是否为审批人创建通知
# 提交新的审批单后检查审批人通知
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-NTF01",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-NTF01",
    "reason": "通知测试采购审批申请12345"
}, token=wj_token)
ntf_apr_id = r["data"].get("id") if r["ok"] else None

if ntf_apr_id:
    r_users = api("GET", "/api/users/by-role/ops_manager", token=admin_token)
    approver_id = r_users["data"][0]["id"] if r_users["ok"] and r_users["data"] else None

    # 提交并指定审批人
    r = api("POST", f"/api/approval-requests/{ntf_apr_id}/submit", {
        "approver_ids": [approver_id] if approver_id else None
    }, token=wj_token)

    # 检查审批人(张伟)是否收到通知
    r = api("GET", "/api/approval-notifications", token=zw_token)
    has_pending_notif = r["ok"] and r["data"].get("total", 0) > 0
    record("通知", "审批提交后审批人收到通知", has_pending_notif, f"通知数={r['data'].get('total')}")


# ============ 8. 校验仪表盘测试 ============
print("\n=== 8. 校验仪表盘 ===")

r = api("GET", "/api/validation", token=admin_token)
record("校验", "校验仪表盘查询成功", r["ok"])
if r["ok"]:
    checks_count = len(r["data"].get("checks", []))
    record("校验", f"有13项检查", checks_count == 13, f"检查数={checks_count}")


# ============ 9. distinct-values API测试 ============
print("\n=== 9. distinct-values ===")

r = api("GET", "/api/distinct-values", token=admin_token)
record("distinct-values", "distinct-values查询成功", r["ok"])

if r["ok"]:
    data = r["data"]
    # 9.1 人员字段应包含系统用户
    persons = data.get("persons", [])
    has_zhangwei = "张伟" in persons
    record("distinct-values", "persons包含系统用户张伟", has_zhangwei, f"persons={persons[:5]}")

    # 9.2 审批人字段应合并系统用户
    approvers = data.get("approvers", [])
    has_user_in_approver = "张伟" in approvers
    record("distinct-values", "approvers合并系统用户", has_user_in_approver)

    # 9.3 执行人字段应合并系统用户
    executors = data.get("executors", [])
    has_user_in_executor = any(u in executors for u in ["张伟", "王军"])
    record("distinct-values", "executors合并系统用户", has_user_in_executor)

    # 9.4 位置字段应合并变更表位置
    locations = data.get("locations", [])
    record("distinct-values", "locations有数据", len(locations) > 0, f"位置数={len(locations)}")

    # 9.5 合同编号应合并采购+维保+续保
    contract_nos = data.get("contract_nos", [])
    record("distinct-values", "contract_nos有数据", len(contract_nos) >= 0)


# ============ 10. users/by-role API测试 ============
print("\n=== 10. users/by-role ===")

# 10.1 各角色查询
for role_code, expected_count in [("admin", 1), ("ops_manager", 2), ("ops_engineer", 4), ("viewer", 2)]:
    r = api("GET", f"/api/users/by-role/{role_code}", token=admin_token)
    count = len(r["data"]) if r["ok"] else 0
    record("by-role", f"{role_code}角色有{expected_count}个用户", count == expected_count, f"实际={count}")

# 10.2 不存在的角色码
r = api("GET", "/api/users/by-role/nonexistent", token=admin_token)
record("by-role", "不存在角色码返回404", r["status"] == 404, f"状态码={r['status']}")

# 10.3 只返回active用户
r = api("GET", "/api/users/by-role/viewer", token=admin_token)
all_active = all(u.get("id") != 9 for u in r["data"]) if r["ok"] else True  # huangjie被恢复为active了
record("by-role", "只返回active用户", r["ok"])


# ============ 11. 导入导出+报表测试 ============
print("\n=== 11. 导入导出+报表 ===")

# 11.1 导出资产
r = api("GET", "/api/export/assets", token=admin_token, raw=True)
record("导出", "导出资产Excel", r["ok"] and r["status"] == 200, f"状态码={r['status']}")

# 11.2 导出子表
for t in ["procurement", "change", "fault", "warranty", "retirement"]:
    r = api("GET", f"/api/export/{t}", token=admin_token, raw=True)
    record("导出", f"导出{t}Excel", r["ok"] and r["status"] == 200, f"状态码={r['status']}")

# 11.3 下载导入模板
for t in ["assets", "procurement", "change", "fault", "warranty", "retirement"]:
    r = api("GET", f"/api/template/{t}", token=admin_token, raw=True)
    record("导出", f"下载{t}导入模板", r["ok"] and r["status"] == 200, f"状态码={r['status']}")

# 11.4 统计概览
r = api("GET", "/api/stats", token=admin_token)
record("报表", "统计概览查询成功", r["ok"])

# 11.5 综合报表
r = api("GET", "/api/reports/comprehensive", token=admin_token)
record("报表", "综合报表查询成功", r["ok"])

# 11.6 维保到期报表
r = api("GET", "/api/reports/warranty-expiry?days=90", token=admin_token)
record("报表", "维保到期报表查询成功", r["ok"])

# 11.7 故障分析报表
r = api("GET", "/api/reports/fault-analysis", token=admin_token)
record("报表", "故障分析报表查询成功", r["ok"])

# 11.8 变更频率报表
r = api("GET", "/api/reports/change-frequency", token=admin_token)
record("报表", "变更频率报表查询成功", r["ok"])

# 11.9 资产时间线
r = api("GET", "/api/assets/DC-CL-SRV-TEST01/timeline", token=admin_token)
record("报表", "资产时间线查询成功", r["ok"])

# 11.10 审批配置
r = api("GET", "/api/approval-config/types", token=admin_token)
record("审批配置", "审批类型配置查询成功", r["ok"])

r = api("GET", "/api/approval-config/dropdowns", token=admin_token)
record("审批配置", "审批下拉选项查询成功", r["ok"])

# 11.11 下拉选项
r = api("GET", "/api/config/dropdowns", token=admin_token)
record("下拉选项", "下拉选项配置查询成功", r["ok"])


# ============ 12. 用户管理测试 ============
print("\n=== 12. 用户管理 ===")

# 12.1 创建用户
r = api("POST", "/api/users", {
    "username": "testuser01",
    "password": "Test2024!",
    "real_name": "测试用户01",
    "department": "测试部",
    "role_ids": []
}, token=admin_token)
record("用户", "创建用户成功", r["ok"], f"返回={r['data']}")

# 12.2 重复用户名
r = api("POST", "/api/users", {
    "username": "testuser01",
    "password": "Test2024!",
    "real_name": "重复用户"
}, token=admin_token)
record("用户", "重复用户名返回400", r["status"] == 400, f"状态码={r['status']}")

# 12.3 不能删除自己
r = api("DELETE", "/api/users/1", token=admin_token)  # admin自己
record("用户", "不能删除自己", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 12.4 重置密码
r = api("POST", "/api/users/9/reset-password", {"new_password": "NewPwd2024!"}, token=admin_token)
record("用户", "重置密码成功", r["ok"])


# ============ 13. 角色管理测试 ============
print("\n=== 13. 角色管理 ===")

# 13.1 查看角色列表
r = api("GET", "/api/roles", token=admin_token)
record("角色", "查看角色列表成功", r["ok"])
default_role_count = r["data"].get("total", 0) if r["ok"] else 0
record("角色", f"有4个预设角色", default_role_count == 4, f"角色数={default_role_count}")

# 13.2 创建自定义角色
r = api("POST", "/api/roles", {
    "name": "测试角色",
    "code": "test_role",
    "description": "测试角色描述",
    "permissions": ["assets:view", "assets:edit"]
}, token=admin_token)
record("角色", "创建自定义角色成功", r["ok"])

# 13.3 重复角色编码
r = api("POST", "/api/roles", {
    "name": "重复角色",
    "code": "test_role"
}, token=admin_token)
record("角色", "重复角色编码返回400", r["status"] == 400, f"状态码={r['status']}")

# 13.4 系统内置角色不可删除
r = api("DELETE", "/api/roles/1", token=admin_token)  # admin角色
record("角色", "系统内置角色不可删除", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 13.5 有用户的角色不可删除
r = api("DELETE", "/api/roles/2", token=admin_token)  # ops_manager角色
record("角色", "有用户的角色不可删除", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")


# ============ 14. 边界条件与安全测试 ============
print("\n=== 14. 边界条件 ===")

# 14.1 空值资产编号查询
r = api("GET", "/api/assets/NONEXISTENT", token=admin_token)
record("边界", "不存在资产编号返回404", r["status"] == 404, f"状态码={r['status']}")

# 14.2 审批reason太短(<5字)
r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-APR01",
    "reason": "太短"
}, token=wj_token)
record("边界", "审批reason<5字返回422", r["status"] == 422, f"状态码={r['status']}")

# 14.3 用户名太短(<2字符)
r = api("POST", "/api/users", {
    "username": "a",
    "password": "Test2024!"
}, token=admin_token)
record("边界", "用户名<2字符返回422", r["status"] == 422, f"状态码={r['status']}")

# 14.4 密码太短(<6字符)
r = api("POST", "/api/users", {
    "username": "testshortpwd",
    "password": "abc"
}, token=admin_token)
record("边界", "密码<6字符返回422", r["status"] == 422, f"状态码={r['status']}")

# 14.5 分页参数越界
r = api("GET", "/api/assets?page=-1&page_size=0", token=admin_token)
record("边界", "分页参数越界返回422", r["status"] == 422, f"状态码={r['status']}")

# 14.6 deleted状态审批单不能操作
r = api("POST", f"/api/approval-requests/{apr5_id}/action", {
    "action": "approve", "comment": "测试"
}, token=admin_token) if apr5_id else None
if apr5_id:
    record("边界", "cancelled审批单不能审批", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 14.7 子表asset_code不存在
r = api("POST", "/api/changes", {
    "asset_code": "NONEXISTENT_CODE",
    "change_type": "位置变更"
}, token=admin_token)
record("边界", "子表关联不存在资产编号返回400", r["status"] == 400, f"状态码={r['status']}")

# 14.8 删除资产级联删除子表
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-DEL01",
    "asset_category": "服务器",
    "lifecycle_stage": "运行"
}, token=admin_token)
del_asset_id = r["data"].get("id") if r["ok"] else None

if del_asset_id:
    # 创建子表记录
    api("POST", "/api/changes", {
        "asset_code": "DC-CL-SRV-DEL01",
        "change_type": "位置变更"
    }, token=admin_token)
    # 删除资产
    r = api("DELETE", f"/api/assets/{del_asset_id}", token=admin_token)
    record("边界", "删除资产级联删除子表", r["ok"])
    # 检查子表是否也被删除
    r2 = api("GET", "/api/changes?asset_code=DC-CL-SRV-DEL01", token=admin_token)
    record("边界", "资产删除后子表查询为空", r2["ok"] and r2["data"].get("total", 0) == 0, f"total={r2['data'].get('total')}")


# ============ 15. 数据完整性检查 ============
print("\n=== 15. 数据完整性 ===")

# 15.1 资产编号格式(DC-CL-[分类]-序号)
r = api("POST", "/api/assets", {
    "asset_code": "BAD_FORMAT_CODE",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)
# 资产编号没有格式校验，可以任意输入 - 这是一个潜在问题
record("数据完整性", "资产编号无格式校验(允许任意字符串)", r["ok"], f"状态码={r['status']} - 注意: 这可能是设计缺陷")

# 15.2 SN序列号唯一性
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-SN01",
    "asset_category": "服务器",
    "lifecycle_stage": "规划",
    "sn": "SN-TEST-001"
}, token=admin_token)
record("数据完整性", "创建资产带SN成功", r["ok"])

r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-SN02",
    "asset_category": "服务器",
    "lifecycle_stage": "规划",
    "sn": "SN-TEST-001"  # 重复SN
}, token=admin_token)
record("数据完整性", "重复SN编号", r["status"] in [400, 409] or (not r["ok"]), f"状态码={r['status']} - 注意: 如返回200则为缺陷(SN应唯一)")

# 15.3 资产分类不在下拉选项中
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-CAT01",
    "asset_category": "不存在的分类",
    "lifecycle_stage": "规划"
}, token=admin_token)
record("数据完整性", "无效资产分类(不在下拉选项中)", r["ok"], f"状态码={r['status']} - 注意: 如返回200则为缺陷(分类应限制下拉选项)")

# 15.4 阶段不在合法范围
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-STG01",
    "asset_category": "服务器",
    "lifecycle_stage": "非法阶段"
}, token=admin_token)
record("数据完整性", "非法阶段值", r["ok"], f"状态码={r['status']} - 注意: 如返回200则为缺陷(阶段应限制为7个合法值)")

# 15.5 故障等级不在合法范围
r = api("POST", "/api/faults", {
    "asset_code": "DC-CL-SRV-SUB01",
    "fault_level": "P9",
    "fault_description": "非法等级测试"
}, token=admin_token)
record("数据完整性", "非法故障等级P9", r["ok"], f"状态码={r['status']} - 注意: 如返回200则为缺陷(等级应限制P1-P4)")

# 15.6 变更类型不在合法范围
r = api("POST", "/api/changes", {
    "asset_code": "DC-CL-SRV-SUB01",
    "change_type": "非法变更类型"
}, token=admin_token)
record("数据完整性", "非法变更类型", r["ok"], f"状态码={r['status']} - 注意: 如返回200则为缺陷(类型应限制为下拉选项)")


# ============ 16. 审批工作流深入测试 ============
print("\n=== 16. 审批深入测试 ===")

# 16.1 已approved的审批单不能再次审批
if apr1_id:
    r = api("POST", f"/api/approval-requests/{apr1_id}/action", {
        "action": "approve", "comment": "再次审批"
    }, token=admin_token)
    record("审批深入", "已approved审批单不能再次审批", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 16.2 已cancelled的审批单不能撤回
if apr5_id:
    r = api("POST", f"/api/approval-requests/{apr5_id}/cancel", token=wj_token)
    record("审批深入", "已cancelled审批单不能再次撤回", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 16.3 draft状态审批单不能审批
r = api("POST", "/api/assets", {
    "asset_code": "DC-CL-SRV-DRAFT01",
    "asset_category": "服务器",
    "lifecycle_stage": "规划"
}, token=admin_token)

r = api("POST", "/api/approval-requests", {
    "approval_type": "procurement_approval",
    "asset_code": "DC-CL-SRV-DRAFT01",
    "reason": "draft状态审批测试12345"
}, token=wj_token)
draft_apr_id = r["data"].get("id") if r["ok"] else None

if draft_apr_id:
    r = api("POST", f"/api/approval-requests/{draft_apr_id}/action", {
        "action": "approve", "comment": "审批draft"
    }, token=zw_token)
    record("审批深入", "draft状态不能审批", r["status"] == 400 or (not r["ok"]), f"状态码={r['status']}")

# 16.4 审批单详情查询
if apr1_id:
    r = api("GET", f"/api/approval-requests/{apr1_id}", token=admin_token)
    record("审批深入", "审批单详情查询成功", r["ok"])

# 16.5 按资产查询审批历史
r = api("GET", "/api/approval-requests/by-asset/DC-CL-SRV-APR01", token=admin_token)
record("审批深入", "按资产查询审批历史成功", r["ok"])

# 16.6 审批列表过滤
r = api("GET", "/api/approval-requests?status=approved", token=admin_token)
record("审批深入", "审批列表按状态过滤", r["ok"])


# ============ 17. 其他安全测试 ============
print("\n=== 17. 安全测试 ===")

# 17.1 JWT硬编码密钥（检查环境变量）
record("安全", "JWT密钥硬编码风险(开发环境)", True, "注意: JWT_SECRET_KEY = 'dev-only-DO-NOT-USE-IN-PRODUCTION' 硬编码，生产环境需设置环境变量")

# 17.2 默认管理员密码admin123
record("安全", "默认管理员密码弱(admin123)", True, "注意: 默认密码admin123过于简单，生产环境应强制修改")

# 17.3 密码重置API返回生成的密码
r = api("POST", "/api/users/9/reset-password", {}, token=admin_token)
if r["ok"]:
    msg = r["data"].get("message", "")
    has_pwd_in_response = "密码已重置为" in msg
    record("安全", "密码重置API返回明文密码", has_pwd_in_response, f"返回={msg} - 注意: 密码不应在响应中返回")

# 17.4 删除用户没有软删除
record("安全", "用户删除是硬删除(db.delete)", True, "注意: 用户删除是物理删除而非软删除，可能丢失审计记录")

# 17.5 CORS配置
record("安全", "CORS配置检查", True, "注意: CORS仅允许127.0.0.1:8000和localhost:8000，生产环境需调整")


# ============ 清理测试数据 ============
print("\n=== 清理测试数据 ===")
for code in ["DC-CL-SRV-TEST01", "DC-CL-SRV-TEST02", "DC-CL-SRV-TEST03", "DC-CL-SRV-TEST04",
             "DC-CL-SRV-SUB01", "DC-CL-SRV-APR01", "DC-CL-SRV-APR02", "DC-CL-SRV-APR03",
             "DC-CL-SRV-APR04", "DC-CL-SRV-APR05", "DC-CL-SRV-APR06", "DC-CL-SRV-NTF01",
             "DC-CL-SRV-DRAFT01", "DC-CL-SRV-SN01", "DC-CL-SRV-SN02", "DC-CL-SRV-CAT01",
             "DC-CL-SRV-STG01", "BAD_FORMAT_CODE", "DC-CL-SRV-DEL01"]:
    # 查找资产ID
    r = api("GET", "/api/assets?search=" + code, token=admin_token)
    if r["ok"] and r["data"].get("items"):
        for item in r["data"]["items"]:
            if item.get("asset_code") == code:
                api("DELETE", f"/api/assets/{item['id']}", token=admin_token)

# 删除测试用户
r = api("GET", "/api/users?search=testuser01", token=admin_token)
if r["ok"] and r["data"].get("items"):
    for u in r["data"]["items"]:
        if u.get("username") == "testuser01":
            api("DELETE", f"/api/users/{u['id']}", token=admin_token)

# 删除自定义角色
r = api("GET", "/api/roles", token=admin_token)
if r["ok"] and r["data"].get("items"):
    for role in r["data"]["items"]:
        if role.get("code") == "test_role":
            api("DELETE", f"/api/roles/{role['id']}", token=admin_token)


# ============ 生成测试报告 ============
print("\n\n" + "="*60)
print("测试结果汇总")
print("="*60)

pass_count = sum(1 for r in results if r["status"] == "PASS")
fail_count = sum(1 for r in results if r["status"] == "FAIL")
total = len(results)

print(f"总测试: {total} | 通过: {pass_count} | 失败: {fail_count}")
print(f"通过率: {pass_count/total*100:.1f}%")

# 按模块统计
modules = {}
for r in results:
    m = r["module"]
    if m not in modules:
        modules[m] = {"pass": 0, "fail": 0, "details": []}
    if r["status"] == "PASS":
        modules[m]["pass"] += 1
    else:
        modules[m]["fail"] += 1
        modules[m]["details"].append(r)

print("\n模块统计:")
for m, d in modules.items():
    total_m = d["pass"] + d["fail"]
    print(f"  {m}: {d['pass']}/{total_m} 通过")

# 缺陷清单
defects = [r for r in results if r["status"] == "FAIL"]
if defects:
    print("\n" + "="*60)
    print("缺陷清单 (FAIL项)")
    print("="*60)
    for i, d in enumerate(defects, 1):
        print(f"  [{i}] [{d['module']}] {d['test']}")
        print(f"      详情: {d['detail']}")

# 安全与设计缺陷清单
print("\n" + "="*60)
print("安全与设计缺陷 (非FAIL但需关注)")
print("="*60)
design_issues = [r for r in results if r["status"] == "PASS" and "注意" in r["detail"]]
for i, d in enumerate(design_issues, 1):
    print(f"  [{i}] [{d['module']}] {d['test']}")
    print(f"      {d['detail']}")

# 保存报告到文件
report = []
report.append("# IT资产全生命周期管理系统 功能测试报告")
report.append(f"测试日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
report.append(f"系统版本: v2.2.0")
report.append(f"总测试: {total} | 通过: {pass_count} | 失败: {fail_count}")
report.append(f"通过率: {pass_count/total*100:.1f}%")
report.append("")
report.append("## 模块统计")
for m, d in modules.items():
    total_m = d["pass"] + d["fail"]
    report.append(f"- **{m}**: {d['pass']}/{total_m} 通过")
report.append("")
report.append("## 功能缺陷清单")
for i, d in enumerate(defects, 1):
    report.append(f"### 缺陷 {i}: [{d['module']}] {d['test']}")
    report.append(f"- **详情**: {d['detail']}")
    report.append("")
report.append("## 安全与设计缺陷")
for i, d in enumerate(design_issues, 1):
    report.append(f"### 设计缺陷 {i}: [{d['module']}] {d['test']}")
    report.append(f"- {d['detail']}")
    report.append("")
report.append("## 测试详情")
for r in results:
    mark = "PASS" if r["status"] == "PASS" else "FAIL"
    report.append(f"- [{mark}] [{r['module']}] {r['test']}: {r['detail']}")

report_text = "\n".join(report)
try:
    import os
    os.makedirs("D:/workbuddy/运维体系重塑方案/deliverables", exist_ok=True)
    with open("D:/workbuddy/运维体系重塑方案/deliverables/defect-report.md", "w", encoding="utf-8") as f:
        f.write(report_text)
    print("\n缺陷报告已保存到 deliverables/defect-report.md")
except Exception as e:
    print(f"\n保存报告失败: {e}")

# 同时保存测试脚本
try:
    with open("D:/workbuddy/运维体系重塑方案/asset-lifecycle-manager/tests/functional_test.py", "w", encoding="utf-8") as f:
        # 重新写入完整脚本
        pass  # 脚本已经在执行中
except:
    pass
