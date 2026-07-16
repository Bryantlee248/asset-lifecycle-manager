"""verify_test_accounts.py — 4 个角色测试账户登录与 RBAC 权限边界独立验证。

验证目标（仅做验证，不修改任何业务代码）：
  1. 登录成功：4 个账户分别 POST /api/auth/login 应返回 200 且 token 非空。
  2. 错误密码拒绝：用错误密码登录应返回 401。
  3. 权限边界（核心断言）：
     - GET /api/users（需 users:view）：test_admin -> 200；其余 3 个 -> 403
     - GET /api/roles（需 roles:view）：test_admin -> 200；其余 3 个 -> 403
     - GET /api/assets?page=1&page_size=1（需 assets:view）：4 个账户全部 -> 200

实现约束：仅使用标准库 urllib.request（不使用 requests 库）。
运行前请确保后端服务已在 http://127.0.0.1:8000 启动，否则脚本会给出明确提示并退出。

用法：
    python verify_test_accounts.py
"""
import json
import sys
import urllib.error
import urllib.request

# ============ 配置 ============
BASE_URL = "http://127.0.0.1:8000"
TEST_PASSWORD = "Test@2026!"
WRONG_PASSWORD = "WrongPass@2026!x"  # 故意错误的密码

# 待测账户（与 backend/auth.py DEFAULT_ROLES 角色 code 对应）
ACCOUNTS = [
    {"username": "test_admin", "role_code": "admin", "is_admin": True},
    {"username": "test_ops_manager", "role_code": "ops_manager", "is_admin": False},
    {"username": "test_ops_engineer", "role_code": "ops_engineer", "is_admin": False},
    {"username": "test_viewer", "role_code": "viewer", "is_admin": False},
]

# 结果收集：[(用例名, 是否通过, 说明), ...]
_RESULTS = []


def record(name, passed, detail=""):
    """记录单条检查结果并打印 PASS/FAIL。"""
    _RESULTS.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _read_body(resp):
    """安全读取响应体并解析为 JSON dict；失败则返回 {}。"""
    try:
        raw = resp.read().decode("utf-8")
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def http_call(method, path, token=None, body=None):
    """发起一次 HTTP 请求，返回 (status_code, data_dict)。

    status_code 为 None 表示连接/网络层面失败。
    """
    url = BASE_URL + path
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, _read_body(resp)
    except urllib.error.HTTPError as e:
        return e.code, _read_body(e)
    except Exception as e:  # 网络不可达等
        return None, {"error": f"{type(e).__name__}: {e}"}


def login(username, password):
    """登录并返回 (status, token_or_None, data)。"""
    status, data = http_call(
        "POST", "/api/auth/login",
        body={"username": username, "password": password},
    )
    token = data.get("token") if isinstance(data, dict) else None
    return status, token, data


def preflight():
    """服务可达性探活（使用公开接口 /api/auth/permissions）。"""
    status, _ = http_call("GET", "/api/auth/permissions")
    if status != 200:
        print("=" * 64)
        print("【前置检查失败】无法访问后端服务 http://127.0.0.1:8000")
        print(f"  探测 /api/auth/permissions 返回状态: {status}")
        print("  请先启动服务：")
        print('    "C:\\Users\\ooo\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe" start.py --production')
        print("=" * 64)
        return False
    return True


def test_login_success(tokens):
    """用例1：4 个账户使用正确密码应登录成功（200 + token 非空）。"""
    for acc in ACCOUNTS:
        status, token, _ = login(acc["username"], TEST_PASSWORD)
        ok = (status == 200 and bool(token))
        record(
            f"登录成功 [{acc['username']}]", ok,
            f"status={status}, token={'非空' if token else '空'}",
        )
        if ok:
            tokens[acc["username"]] = token


def test_wrong_password_rejected():
    """用例2：错误密码登录应返回 401（覆盖 admin 与 viewer 两类角色）。"""
    for acc in (ACCOUNTS[0], ACCOUNTS[3]):  # test_admin, test_viewer
        status, _, _ = login(acc["username"], WRONG_PASSWORD)
        record(
            f"错误密码被拒绝 [{acc['username']}]", status == 401,
            f"status={status} (期望 401)",
        )


def test_permission_boundaries(tokens):
    """用例3：核心权限边界断言。"""
    for acc in ACCOUNTS:
        token = tokens.get(acc["username"])
        if not token:
            record(f"权限边界 [所有接口] [{acc['username']}]", False, "无 token（登录失败，跳过）")
            continue

        # (端点, 期望状态, 说明)
        cases = [
            ("/api/users", 200 if acc["is_admin"] else 403, "users:view"),
            ("/api/roles", 200 if acc["is_admin"] else 403, "roles:view"),
            ("/api/assets?page=1&page_size=1", 200, "assets:view"),
        ]
        for path, expected, perm in cases:
            status, _ = http_call("GET", path, token=token)
            ok = (status == expected)
            record(
                f"权限边界 GET {path} [{acc['username']}]", ok,
                f"需要 {perm}, 期望 {expected}, 实际 {status}",
            )


def main():
    print("=" * 64)
    print("IT 资产全生命周期管理系统 — 测试账户登录与 RBAC 权限验证")
    print("=" * 64)

    if not preflight():
        sys.exit(2)

    tokens = {}
    print("\n--- 用例1: 登录成功 ---")
    test_login_success(tokens)

    print("\n--- 用例2: 错误密码拒绝 (401) ---")
    test_wrong_password_rejected()

    print("\n--- 用例3: 权限边界 (核心断言) ---")
    test_permission_boundaries(tokens)

    # 汇总
    total = len(_RESULTS)
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    failed = total - passed
    print("\n" + "=" * 64)
    print(f"总体结论: {'PASS' if failed == 0 else 'FAIL'}")
    print(f"用例总数: {total} | 通过: {passed} | 失败: {failed}")
    print("=" * 64)

    # 路由判定（供 QA 流程使用）
    if failed == 0:
        print("智能路由判定: NoOne（全部通过，无需处理）")
    else:
        print("智能路由判定: 需分析失败项（权限逻辑错误→Engineer；脚本问题→QA 自检修复）")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
