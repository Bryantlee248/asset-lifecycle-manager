"""深度缺陷验证脚本"""
import urllib.request
import json
import urllib.parse

BASE = "http://127.0.0.1:8000"

def api(method, path, data=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        try:
            result = json.loads(resp.read().decode("utf-8"))
        except:
            result = resp.read().decode("utf-8", errors="replace")
        return {"status": resp.status, "data": result, "ok": True}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except:
            body = e.read().decode("utf-8", errors="replace")
        return {"status": e.code, "data": body, "ok": False}

def login(u, p):
    r = api("POST", "/api/auth/login", {"username": u, "password": p})
    return r["data"].get("token") if r["ok"] else None

tk = login("admin", "admin123")

# 1. SN duplicate returns 500
print("=== 1. SN duplicate 500 error ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-SN01", "asset_category": "服务器", "lifecycle_stage": "规划", "sn": "SN-DUP-001"}, token=tk)
print("Create asset1 with SN:", r["ok"])
r = api("POST", "/api/assets", {"asset_code": "DC-CL-SN02", "asset_category": "服务器", "lifecycle_stage": "规划", "sn": "SN-DUP-001"}, token=tk)
print("Create asset2 duplicate SN: status=" + str(r["status"]) + " | data=" + str(r["data"])[:300])

# 2. P1 fault creation
print("\n=== 2. P1 fault creation ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-P1T", "asset_category": "服务器", "lifecycle_stage": "运行"}, token=tk)
aid = r["data"].get("id") if r["ok"] else None
print("Create running asset: ok=" + str(r["ok"]) + " id=" + str(aid))
if aid:
    r = api("POST", "/api/faults", {"asset_code": "DC-CL-P1T", "fault_level": "P1", "fault_description": "server crash", "fault_date": "2026-06-25"}, token=tk)
    print("Create P1 fault: ok=" + str(r["ok"]) + " status=" + str(r["status"]))
    if r["ok"]:
        r2 = api("GET", "/api/assets/DC-CL-P1T", token=tk)
        print("  Stage after P1: " + str(r2["data"]["lifecycle_stage"]))
        r3 = api("GET", "/api/approval-requests?asset_code=DC-CL-P1T", token=tk)
        print("  Approval count: " + str(r3["data"].get("total", 0)))
    else:
        print("  Error: " + str(r["data"])[:200])

# 3. Fault on retired asset
print("\n=== 3. Fault on retired asset ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-RET", "asset_category": "服务器", "lifecycle_stage": "已报废"}, token=tk)
print("Create retired asset: ok=" + str(r["ok"]))
if r["ok"]:
    r = api("POST", "/api/faults", {"asset_code": "DC-CL-RET", "fault_level": "P3", "fault_description": "fault on retired"}, token=tk)
    print("Create fault on retired: ok=" + str(r["ok"]) + " status=" + str(r["status"]) + " - should this be allowed?")

# 4. Warranty renewal approval (stage unchanged)
print("\n=== 4. Warranty renewal approval ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-W01", "asset_category": "服务器", "lifecycle_stage": "运行"}, token=tk)
if r["ok"]:
    r = api("POST", "/api/approval-requests", {"approval_type": "warranty_renewal_approval", "asset_code": "DC-CL-W01", "reason": "warranty renewal test need 5 chars min 12345"}, token=tk)
    print("Create warranty renewal: ok=" + str(r["ok"]))
    wid = r["data"].get("id") if r["ok"] else None
    if wid:
        r = api("POST", "/api/approval-requests/" + str(wid) + "/submit", {}, token=tk)
        print("Submit: ok=" + str(r["ok"]))
        r = api("POST", "/api/approval-requests/" + str(wid) + "/action", {"action": "approve", "comment": "ok"}, token=tk)
        print("Approve: ok=" + str(r["ok"]))
        if r["ok"]:
            r2 = api("GET", "/api/assets/DC-CL-W01", token=tk)
            print("  Stage after approval: " + str(r2["data"]["lifecycle_stage"]) + " (should remain running)")

# 5. P1 fault on transit asset
print("\n=== 5. P1 fault on transit asset ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-P1TR", "asset_category": "服务器", "lifecycle_stage": "在途"}, token=tk)
if r["ok"]:
    r = api("POST", "/api/faults", {"asset_code": "DC-CL-P1TR", "fault_level": "P1", "fault_description": "transit fault", "fault_date": "2026-06-25"}, token=tk)
    print("Create P1 fault on transit: ok=" + str(r["ok"]))
    if r["ok"]:
        r2 = api("GET", "/api/assets/DC-CL-P1TR", token=tk)
        print("  Stage after P1 on transit: " + str(r2["data"]["lifecycle_stage"]))

# 6. P1 fault on repair asset (already in repair)
print("\n=== 6. P1 fault on already-repair asset ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-P1RP", "asset_category": "服务器", "lifecycle_stage": "维修"}, token=tk)
if r["ok"]:
    r = api("POST", "/api/faults", {"asset_code": "DC-CL-P1RP", "fault_level": "P1", "fault_description": "repair fault", "fault_date": "2026-06-25"}, token=tk)
    print("Create P1 fault on repair: ok=" + str(r["ok"]))
    if r["ok"]:
        r2 = api("GET", "/api/assets/DC-CL-P1RP", token=tk)
        print("  Stage after P1 on repair: " + str(r2["data"]["lifecycle_stage"]))
        r3 = api("GET", "/api/approval-requests?asset_code=DC-CL-P1RP", token=tk)
        for item in r3["data"].get("items", []):
            if item["approval_type"] == "fault_degrade_approval":
                print("  Auto approval status: " + str(item["status"]))

# 7. Check null approver_id
print("\n=== 7. Check null approver_id ===")
r = api("GET", "/api/approval-requests?page=1&page_size=20", token=tk)
null_count = 0
for item in r["data"].get("items", []):
    for step in item.get("steps", []):
        if step.get("approver_id") is None:
            null_count += 1
            print("  Null approver_id: " + str(item["request_no"]) + " step_id=" + str(step["id"]))
print("Total null approver steps: " + str(null_count))

# 8. Invalid enum values
print("\n=== 8. Invalid enum values ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-EV01", "asset_category": "非法分类", "lifecycle_stage": "非法阶段"}, token=tk)
print("Invalid category+stage: ok=" + str(r["ok"]) + " status=" + str(r["status"]))

r = api("POST", "/api/faults", {"asset_code": "DC-CL-P1T", "fault_level": "P9", "fault_description": "test"}, token=tk)
print("Invalid fault level P9: ok=" + str(r["ok"]) + " status=" + str(r["status"]))

r = api("POST", "/api/changes", {"asset_code": "DC-CL-P1T", "change_type": "非法类型"}, token=tk)
print("Invalid change type: ok=" + str(r["ok"]) + " status=" + str(r["status"]))

# 9. Repair->Run without fault record
print("\n=== 9. Repair->Run without any fault ===")
r = api("POST", "/api/assets", {"asset_code": "DC-CL-NF01", "asset_category": "服务器", "lifecycle_stage": "维修"}, token=tk)
aid_nf = r["data"].get("id") if r["ok"] else None
if aid_nf:
    r = api("GET", "/api/assets/DC-CL-NF01/stage-gate/" + urllib.parse.quote("运行"), token=tk)
    print("Stage gate (repair->run, no fault): " + json.dumps(r["data"], ensure_ascii=False))
    r = api("PUT", "/api/assets/" + str(aid_nf), {"lifecycle_stage": "运行"}, token=tk)
    print("PUT repair->run (no fault): ok=" + str(r["ok"]) + " status=" + str(r["status"]))
    if r["ok"]:
        print("  **DEFECT CONFIRMED**: Repair->Run allowed without fault record!")

# 10. Password reset returns plaintext
print("\n=== 10. Password reset response ===")
r = api("POST", "/api/users/9/reset-password", {}, token=tk)
if r["ok"]:
    print("Reset password response: " + str(r["data"]))

# Cleanup
print("\n=== Cleanup ===")
for code in ["DC-CL-SN01", "DC-CL-SN02", "DC-CL-P1T", "DC-CL-RET", "DC-CL-W01", "DC-CL-P1TR", "DC-CL-P1RP", "DC-CL-EV01", "DC-CL-NF01"]:
    r = api("GET", "/api/assets?search=" + urllib.parse.quote(code), token=tk)
    if r["ok"] and r["data"].get("items"):
        for item in r["data"]["items"]:
            if item.get("asset_code") == code:
                api("DELETE", "/api/assets/" + str(item["id"]), token=tk)
                print("  Cleaned: " + code)
