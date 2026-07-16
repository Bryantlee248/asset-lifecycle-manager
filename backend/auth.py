"""认证与权限管理模块 - JWT + RBAC — 新台账模板v1.0"""
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from functools import wraps

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext

from settings import load_settings
from database import get_db, User, Role

# ============ JWT 配置 ============
# 密钥优先级: 环境变量 > 配置文件(.jwt_secret) > 开发随机生成(.jwt_dev_key)
# 生产环境必须通过环境变量或 .jwt_secret 配置文件提供固定密钥
# 开发环境使用 .jwt_dev_key 自动生成随机密钥
settings = load_settings()
JWT_SECRET_KEY = settings.jwt_secret_key
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if not JWT_SECRET_KEY:
    # 1. 生产密钥配置文件（部署时手动写入固定密钥）
    _prod_key_file = os.path.join(_backend_dir, ".jwt_secret")
    if os.path.exists(_prod_key_file):
        with open(_prod_key_file, "r") as f:
            JWT_SECRET_KEY = f.read().strip()
    if not JWT_SECRET_KEY:
        if os.environ.get("ENV") == "production":
            raise RuntimeError(
                "生产环境必须提供 JWT 密钥:\n"
                "  方式1: 设置环境变量 JWT_SECRET_KEY\n"
                "  方式2: 在 backend/ 目录下创建 .jwt_secret 文件写入密钥\n"
                "  生成密钥命令: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # 开发环境自动生成随机密钥（每次重启不变，存在 .jwt_dev_key）
        _dev_key_file = os.path.join(_backend_dir, ".jwt_dev_key")
        if os.path.exists(_dev_key_file):
            with open(_dev_key_file, "r") as f:
                JWT_SECRET_KEY = f.read().strip()
        if not JWT_SECRET_KEY:
            JWT_SECRET_KEY = secrets.token_hex(32)
            with open(_dev_key_file, "w") as f:
                f.write(JWT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# ============ bcrypt 密码哈希 ============
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """bcrypt密码哈希"""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed: str) -> bool:
    """验证密码"""
    return _pwd_context.verify(plain_password, hashed)


def create_access_token(data: dict) -> str:
    """生成JWT Token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户（依赖注入）"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证信息")

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token无效或已过期")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token无效")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")

    if user.status != "active":
        raise HTTPException(status_code=403, detail="账户已被禁用")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """可选获取当前用户（未登录返回None）"""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def get_user_permissions(user: User) -> list:
    """获取用户所有权限（合并所有角色的权限）"""
    perms = set()
    for role in user.roles:
        if role.permissions:
            try:
                role_perms = json.loads(role.permissions)
                perms.update(role_perms)
            except (json.JSONDecodeError, TypeError):
                pass
    return list(perms)


def get_user_role_codes(user: User) -> list:
    """获取用户所有角色编码"""
    return [r.code for r in user.roles]


def require_permission(permission: str):
    """权限检查装饰器工厂"""
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        # 系统管理员拥有所有权限
        role_codes = get_user_role_codes(current_user)
        if "admin" in role_codes:
            return current_user

        # 检查具体权限
        user_perms = get_user_permissions(current_user)
        if permission not in user_perms:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足，需要权限: {permission}"
            )
        return current_user
    return permission_checker


def require_any_permission(*permissions: str):
    """需要任一权限"""
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        role_codes = get_user_role_codes(current_user)
        if "admin" in role_codes:
            return current_user

        user_perms = get_user_permissions(current_user)
        if not any(p in user_perms for p in permissions):
            raise HTTPException(
                status_code=403,
                detail=f"权限不足，需要以下权限之一: {', '.join(permissions)}"
            )
        return current_user
    return permission_checker


# ============ 默认角色和权限定义 ============
PERMISSION_DEFINITIONS = {
    # 概览
    "dashboard:view": "查看数据总览",
    "validation:view": "查看校验仪表盘",
    # 数据交换
    "import_export:view": "查看导入导出",
    "import_export:import": "执行数据导入",
    "import_export:export": "执行数据导出",
    # 报表
    "reports:view": "查看报表统计",
    # 资产台账
    "assets:view": "查看资产台账",
    "assets:create": "新增资产",
    "assets:edit": "编辑资产",
    "assets:delete": "删除资产",
    # 采购入库
    "procurement:view": "查看采购入库",
    "procurement:create": "新增采购记录",
    "procurement:edit": "编辑采购记录",
    "procurement:delete": "删除采购记录",
    # 资产移入（新增）
    "inbound:view": "查看资产移入",
    "inbound:create": "新增移入记录",
    "inbound:edit": "编辑移入记录",
    "inbound:delete": "删除移入记录",
    # 资产移出（新增）
    "outbound:view": "查看资产移出",
    "outbound:create": "新增移出记录",
    "outbound:edit": "编辑移出记录",
    "outbound:delete": "删除移出记录",
    # 变更迁移
    "change:view": "查看变更迁移",
    "change:create": "新增变更记录",
    "change:edit": "编辑变更记录",
    "change:delete": "删除变更记录",
    # 故障维修
    "fault:view": "查看故障维修",
    "fault:create": "新增故障记录",
    "fault:edit": "编辑故障记录",
    "fault:delete": "删除故障记录",
    # 维保续保
    "warranty:view": "查看维保续保",
    "warranty:create": "新增维保记录",
    "warranty:edit": "编辑维保记录",
    "warranty:delete": "删除维保记录",
    # 退役报废
    "retirement:view": "查看退役报废",
    "retirement:create": "新增退役记录",
    "retirement:edit": "编辑退役记录",
    "retirement:delete": "删除退役记录",
    # 系统管理
    "users:view": "查看用户管理",
    "users:create": "新增用户",
    "users:edit": "编辑用户",
    "users:delete": "删除用户",
    "roles:view": "查看角色管理",
    "roles:create": "新增角色",
    "roles:edit": "编辑角色",
    "roles:delete": "删除角色",
    # 审批工作流
    "approval:view": "查看审批工作流",
    "approval:submit": "提交/撤回审批申请",
    "approval:approve": "审批操作（通过/驳回）",
    "approval:cancel": "取消审批申请",
    "approval_template:manage": "审批模板管理（编辑审批流配置）",
    # 系统配置
    "config:manage": "系统配置管理",
}

# 权限分组（前端展示用）
PERMISSION_GROUPS = [
    {
        "name": "概览",
        "permissions": ["dashboard:view", "validation:view"]
    },
    {
        "name": "数据交换",
        "permissions": ["import_export:view", "import_export:import", "import_export:export"]
    },
    {
        "name": "报表统计",
        "permissions": ["reports:view"]
    },
    {
        "name": "资产台账",
        "permissions": ["assets:view", "assets:create", "assets:edit", "assets:delete"]
    },
    {
        "name": "采购入库",
        "permissions": ["procurement:view", "procurement:create", "procurement:edit", "procurement:delete"]
    },
    {
        "name": "资产移入",
        "permissions": ["inbound:view", "inbound:create", "inbound:edit", "inbound:delete"]
    },
    {
        "name": "资产移出",
        "permissions": ["outbound:view", "outbound:create", "outbound:edit", "outbound:delete"]
    },
    {
        "name": "变更迁移",
        "permissions": ["change:view", "change:create", "change:edit", "change:delete"]
    },
    {
        "name": "故障维修",
        "permissions": ["fault:view", "fault:create", "fault:edit", "fault:delete"]
    },
    {
        "name": "维保续保",
        "permissions": ["warranty:view", "warranty:create", "warranty:edit", "warranty:delete"]
    },
    {
        "name": "退役报废",
        "permissions": ["retirement:view", "retirement:create", "retirement:edit", "retirement:delete"]
    },
    {
        "name": "用户管理",
        "permissions": ["users:view", "users:create", "users:edit", "users:delete"]
    },
    {
        "name": "角色管理",
        "permissions": ["roles:view", "roles:create", "roles:edit", "roles:delete"]
    },
    {
        "name": "审批工作流",
        "permissions": ["approval:view", "approval:submit", "approval:approve", "approval:cancel", "approval_template:manage"]
    },
    {
        "name": "系统管理",
        "permissions": ["config:manage"]
    },
]

# 预设角色
DEFAULT_ROLES = [
    {
        "name": "系统管理员",
        "code": "admin",
        "description": "拥有系统全部权限，可管理用户和角色",
        "permissions": list(PERMISSION_DEFINITIONS.keys()),  # 50项全权限
        "is_system": True
    },
    {
        "name": "运维主管",
        "code": "ops_manager",
        "description": "管理所有资产数据，查看报表和校验，不可管理用户",
        "permissions": [
            "dashboard:view", "validation:view",
            "import_export:view", "import_export:import", "import_export:export",
            "reports:view",
            "assets:view", "assets:create", "assets:edit", "assets:delete",
            "procurement:view", "procurement:create", "procurement:edit", "procurement:delete",
            "inbound:view", "inbound:create", "inbound:edit", "inbound:delete",
            "outbound:view", "outbound:create", "outbound:edit", "outbound:delete",
            "change:view", "change:create", "change:edit", "change:delete",
            "fault:view", "fault:create", "fault:edit", "fault:delete",
            "warranty:view", "warranty:create", "warranty:edit", "warranty:delete",
            "retirement:view", "retirement:create", "retirement:edit", "retirement:delete",
            "approval:view", "approval:submit", "approval:approve", "approval:cancel",
            "config:manage",
        ],
        "is_system": True
    },
    {
        "name": "运维工程师",
        "code": "ops_engineer",
        "description": "查看和编辑资产数据，不可删除记录，不可管理用户",
        "permissions": [
            "dashboard:view", "validation:view",
            "import_export:view", "import_export:export",
            "reports:view",
            "assets:view", "assets:create", "assets:edit",
            "procurement:view", "procurement:create", "procurement:edit",
            "inbound:view", "inbound:create",
            "outbound:view", "outbound:create",
            "change:view", "change:create", "change:edit",
            "fault:view", "fault:create", "fault:edit",
            "warranty:view", "warranty:create", "warranty:edit",
            "retirement:view", "retirement:create", "retirement:edit",
            "approval:view", "approval:submit",
        ],
        "is_system": True
    },
    {
        "name": "只读用户",
        "code": "viewer",
        "description": "仅可查看数据，不可增删改",
        "permissions": [
            "dashboard:view", "validation:view",
            "import_export:view", "import_export:export",
            "reports:view",
            "assets:view", "procurement:view", "change:view",
            "fault:view", "warranty:view", "retirement:view",
            "inbound:view", "outbound:view",
            "approval:view",
        ],
        "is_system": True
    },
]

DEFAULT_ADMIN = {
    "username": "admin",
    "real_name": "系统管理员",
    "department": "信息中心",
    "status": "active"
}


def get_bootstrap_admin_password(db: Session) -> str | None:
    existing_admin = db.query(User).filter(User.username == "admin").first()
    password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()
    if existing_admin is None and os.environ.get("ENV", "development").lower() == "production" and not password:
        raise RuntimeError("Production first startup requires DEFAULT_ADMIN_PASSWORD")
    return password or None


def init_default_data(db: Session):
    """初始化默认角色和管理员账号（含权限合并逻辑）"""
    # 创建默认角色或合并权限
    for role_data in DEFAULT_ROLES:
        existing = db.query(Role).filter(Role.code == role_data["code"]).first()
        if not existing:
            role = Role(
                name=role_data["name"],
                code=role_data["code"],
                description=role_data["description"],
                permissions=json.dumps(role_data["permissions"], ensure_ascii=False),
                is_system=role_data["is_system"]
            )
            db.add(role)
        else:
            # 权限合并逻辑：如果已有角色权限不含新增审批权限，自动追加
            existing_perms = json.loads(existing.permissions) if existing.permissions else []
            new_perms = [p for p in role_data["permissions"] if p not in existing_perms]
            if new_perms:
                existing_perms.extend(new_perms)
                existing.permissions = json.dumps(existing_perms, ensure_ascii=False)

    db.commit()

    # 创建默认管理员
    admin_role = db.query(Role).filter(Role.code == "admin").first()
    existing_admin = db.query(User).filter(User.username == DEFAULT_ADMIN["username"]).first()
    bootstrap_password = get_bootstrap_admin_password(db)
    if not existing_admin and admin_role and bootstrap_password:
        admin = User(
            username=DEFAULT_ADMIN["username"],
            password_hash=hash_password(bootstrap_password),
            real_name=DEFAULT_ADMIN["real_name"],
            department=DEFAULT_ADMIN["department"],
            status=DEFAULT_ADMIN["status"]
        )
        admin.roles.append(admin_role)
        db.add(admin)
        db.commit()
