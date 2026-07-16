"""为 IT 资产全生命周期管理系统 v3.0.0 的每个内置角色创建测试账户。

脚本特征：
- 直写 SQLite 数据库（复用 backend/database.py 的 engine，已指向正确的 DB）
- 幂等可重跑：对每个目标用户名，若已存在则跳过创建，仅输出"已存在，跳过"；
  若角色关联缺失则补全关联，保证重跑不产生重复账户
- 为每个内置角色创建 test_<role_code> 测试账户
- 统一测试密码 Test@2026!（满足复杂度要求：大小写 + 数字 + 特殊字符）
- 运行结束后打印各账户创建/跳过状态、各角色账户数汇总，并反向验证密码

用法：
    python generate_test_accounts.py
（必须使用项目指定的 Python 运行时）
"""

import os
import sys

# ============ 将 backend 加入 sys.path ============
# 脚本位于项目根目录，backend 模块在 backend/ 子目录下
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from database import SessionLocal, User, Role  # noqa: E402
from auth import hash_password, verify_password  # noqa: E402

# ============ 统一测试账户配置 ============
TEST_PASSWORD = "Test@2026!"
TEST_DEPARTMENT = "信息中心"
TEST_PHONE = "13800000000"

# 每个内置角色对应的测试账户定义
# code: 角色编码；username: 测试用户名；real_name: 真实姓名；email: 邮箱
TEST_ACCOUNTS = [
    {
        "username": "test_admin",
        "role_code": "admin",
        "real_name": "测试-系统管理员",
        "email": "test_admin@example.com",
    },
    {
        "username": "test_ops_manager",
        "role_code": "ops_manager",
        "real_name": "测试-运维主管",
        "email": "test_ops_manager@example.com",
    },
    {
        "username": "test_ops_engineer",
        "role_code": "ops_engineer",
        "real_name": "测试-运维工程师",
        "email": "test_ops_engineer@example.com",
    },
    {
        "username": "test_viewer",
        "role_code": "viewer",
        "real_name": "测试-只读用户",
        "email": "test_viewer@example.com",
    },
]


def ensure_account(db, spec):
    """确保某个角色的测试账户存在且关联正确。

    Args:
        db: SQLAlchemy 会话
        spec: 测试账户定义字典

    Returns:
        tuple: (status: str, user: User)
        status 取值："created" / "skipped" / "relinked"
    """
    username = spec["username"]
    role_code = spec["role_code"]

    # 1) 查找对应角色（按 code）
    role = db.query(Role).filter(Role.code == role_code).first()
    if role is None:
        raise RuntimeError(
            f"角色 code={role_code} 不存在，请先初始化默认角色数据后再运行本脚本"
        )

    # 2) 查找是否已存在该用户名
    user = db.query(User).filter(User.username == username).first()
    if user is not None:
        # 已存在：跳过创建；若角色关联缺失则补关联
        role_codes = {r.code for r in user.roles}
        if role_code not in role_codes:
            user.roles.append(role)
            db.commit()
            print(f"  [补关联] 用户 {username} 已存在，已补挂角色 {role_code}")
            return "relinked", user
        print(f"  [跳过] 用户 {username} 已存在，跳过创建")
        return "skipped", user

    # 3) 不存在：创建新用户并挂载角色
    user = User(
        username=username,
        password_hash=hash_password(TEST_PASSWORD),
        real_name=spec["real_name"],
        email=spec["email"],
        phone=TEST_PHONE,
        department=TEST_DEPARTMENT,
        status="active",
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    print(f"  [创建] 用户 {username}（角色 {role_code}）创建成功")
    return "created", user


def summarize_by_role(db):
    """统计每个内置角色下的账户数。

    Args:
        db: SQLAlchemy 会话

    Returns:
        dict: {role_code: 账户数}
    """
    summary = {}
    roles = db.query(Role).all()
    for role in roles:
        summary[role.code] = len(role.users)
    return summary


def verify_passwords(db, specs):
    """反向验证测试账户密码是否正确。

    Args:
        db: SQLAlchemy 会话
        specs: 测试账户定义列表

    Returns:
        bool: 全部验证通过返回 True，否则 False
    """
    all_ok = True
    print("\n[密码反向验证]")
    for spec in specs:
        user = db.query(User).filter(User.username == spec["username"]).first()
        if user is None:
            print(f"  [失败] 用户 {spec['username']} 不存在，无法验证")
            all_ok = False
            continue
        ok = verify_password(TEST_PASSWORD, user.password_hash)
        status = "通过" if ok else "失败"
        print(f"  [{status}] {spec['username']} 密码验证 {'OK' if ok else 'ERROR'}")
        if not ok:
            all_ok = False
    return all_ok


def main():
    """主流程：创建/校验测试账户并打印汇总。"""
    db = SessionLocal()
    try:
        print("=" * 60)
        print("IT 资产全生命周期管理系统 v3.0.0 — 测试账户生成")
        print("=" * 60)

        results = []
        for spec in TEST_ACCOUNTS:
            print(f"\n处理角色 {spec['role_code']} -> 目标账户 {spec['username']}")
            status, user = ensure_account(db, spec)
            results.append((spec, status, user))

        # 各角色账户数汇总
        print("\n" + "=" * 60)
        print("各角色账户数汇总")
        print("=" * 60)
        summary = summarize_by_role(db)
        # 按 TEST_ACCOUNTS 顺序 + 其余角色输出
        ordered_codes = [s["role_code"] for s in TEST_ACCOUNTS]
        for code in ordered_codes:
            print(f"  {code:<14}: {summary.get(code, 0)} 个账户")
        # 输出其他可能存在的内置/自定义角色
        for code, count in summary.items():
            if code not in ordered_codes:
                print(f"  {code:<14}: {count} 个账户（非本次目标角色）")

        # 账户与角色对应关系明细
        print("\n" + "=" * 60)
        print("测试账户与角色对应关系")
        print("=" * 60)
        for spec, status, user in results:
            role_codes = ", ".join(r.code for r in user.roles) or "(无)"
            print(
                f"  {user.username:<18} | 角色: {role_codes:<30} | "
                f"状态: {status:<8} | real_name: {user.real_name}"
            )

        # 密码反向验证
        print()
        passwords_ok = verify_passwords(db, TEST_ACCOUNTS)

        print("\n" + "=" * 60)
        if passwords_ok:
            print("完成：所有测试账户已就位，密码验证全部通过。")
        else:
            print("警告：存在密码验证失败的账户，请检查。")
        print("=" * 60)

        return passwords_ok
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    # 0 表示成功，1 表示存在异常/验证失败
    sys.exit(0 if success else 1)
