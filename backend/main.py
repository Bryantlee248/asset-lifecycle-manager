"""FastAPI主应用 - IT资产全生命周期管理系统（新台账模板v1.0）"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime, timedelta, timezone, time
import json
import os
import re

from database import (
    get_db, Asset, Procurement, Change, Fault, Warranty, Retirement,
    AssetInbound, AssetOutbound, Dictionary, Category,
    User, Role, AuditLog, ApprovalRequest, ApprovalStep, ApprovalNotification,
    WorkflowTemplate, record_stage_change
)
from auth import (
    hash_password, verify_password, create_access_token, get_current_user,
    get_current_user_optional, get_user_permissions, get_user_role_codes,
    require_permission, require_any_permission,
    init_default_data, PERMISSION_DEFINITIONS, PERMISSION_GROUPS
)
from approval import (
    submit_approval, process_approval_action, cancel_approval,
    resubmit_approval, auto_submit_fault_approval,
    outbound_retirement_auto_submit, generate_request_no
)
from workflow_engine import WorkflowEngine
from seed_workflow_templates import seed_workflow_templates
from config_cache import build_enum_cache, invalidate_and_rebuild, DROPDOWN_FIELD_TO_SOURCE
from seed_config_dict import seed_config_dict
from seed_stage_transitions import seed_stage_transitions
from seed_p2_config import seed_p2_config
from import_export_reports import (
    import_assets_excel, import_subtable_excel,
    export_assets_excel, export_subtable_excel, download_import_template,
    get_comprehensive_report, get_warranty_expiry_report,
    get_fault_analysis_report, get_change_frequency_report
)
from reports_stats import stats_router
from config_api import config_router
from health import health_router
from schemas import (
    AssetCreate, AssetUpdate, AssetResponse,
    ProcurementCreate, ProcurementUpdate, ProcurementResponse,
    ChangeCreate, ChangeUpdate, ChangeResponse,
    FaultCreate, FaultUpdate, FaultResponse,
    WarrantyCreate, WarrantyUpdate, WarrantyResponse,
    RetirementCreate, RetirementUpdate, RetirementResponse,
    InboundCreate, InboundUpdate, InboundResponse,
    OutboundCreate, OutboundUpdate, OutboundResponse,
    ValidationDashboard, DropdownConfig, StageGateResult,
    LoginRequest, LoginResponse, ChangePasswordRequest, ResetPasswordRequest,
    UserCreate, UserUpdate, UserResponse,
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionGroup, PermissionInfo, PermissionConfig,
    RoleBrief,
    ApprovalRequestCreate, ApprovalActionRequest, ApprovalRequestResubmit, ApprovalSubmitRequest,
    ApprovalRequestResponse, ApprovalStepResponse, ApprovalNotificationResponse,
    ApprovalStatsResponse, ApprovalTypeConfigItem, ApprovalDropdownConfig
)
from validation import run_all_checks, check_stage_gate
from settings import load_settings
from audit import record_audit
from constants import (
    LIFECYCLE_STAGES, ACTIVE_STAGES,
    APPROVAL_TYPES, APPROVAL_TYPE_NAMES, APPROVAL_STATUSES
)


# ============ 辅助函数 ============
def parse_location(loc_str: str) -> dict:
    """解析位置字符串为room/cabinet/u_position（与migrate.py相同逻辑）"""
    import re as _re
    result = {"room": None, "cabinet": None, "u_position": None}
    if not loc_str:
        return result
    # 格式1: "5-4机房-R-03-15-16U" → room=5-4机房, cabinet=R-03, u_position=15-16U
    m1 = _re.match(r'^([\w\-]+机房)\-([A-Z]-\d+)\-(.+U)$', loc_str)
    if m1:
        result["room"], result["cabinet"], result["u_position"] = m1.groups()
        return result
    # 格式2: "505-R-02-U38" → room=505, cabinet=R-02, u_position=U38
    m2 = _re.match(r'^(\d+)\-([A-Z]-\d+)\-(U\d+)$', loc_str)
    if m2:
        result["room"], result["cabinet"], result["u_position"] = m2.groups()
        return result
    # 格式3: "A栋1楼机房A1 B08U4" → room=A栋1楼机房A1, cabinet=B08, u_position=U4
    m3 = _re.match(r'^([\w\u4e00-\u9fff]+)\s*([A-Z]\d+)\s*(U\d+)$', loc_str)
    if m3:
        result["room"], result["cabinet"], result["u_position"] = m3.groups()
        return result
    # 格式4: 无法解析 → room=原值
    result["room"] = loc_str
    return result


def _audit_create(db: Session, current_user: User, resource_type: str, resource_id: str, after: dict) -> None:
    record_audit(
        db,
        current_user.id,
        "create",
        resource_type,
        resource_id,
        {"after": after},
    )


def _audit_update(
    db: Session, current_user: User, resource_type: str, resource_id: str,
    before: dict, after: dict,
) -> None:
    record_audit(
        db,
        current_user.id,
        "update",
        resource_type,
        resource_id,
        {"before": before, "after": after},
    )


def _audit_delete(
    db: Session, current_user: User, resource_type: str, resource_id: str, before: dict
) -> None:
    record_audit(
        db,
        current_user.id,
        "delete",
        resource_type,
        resource_id,
        {"before": before},
    )


# ============ Lifespan ============
@asynccontextmanager
async def lifespan(app):
    db = next(get_db())
    try:
        init_default_data(db)
        seed_workflow_templates(db)
        # 系统配置模块 P0：种子字典/分类 + 启动期构建枚举缓存（单一数据源）
        seed_config_dict(db)
        seed_stage_transitions(db)
        seed_p2_config(db)
        invalidate_and_rebuild(db)
    finally:
        db.close()
    yield


app = FastAPI(title="IT资产全生命周期管理系统", version="3.0.0", lifespan=lifespan)

# BUG-014 修复：CORS支持可配置来源列表
_default_origins = [
    "http://127.0.0.1:8000", "http://localhost:8000",
    "http://127.0.0.1:3000", "http://localhost:3000",
    "http://127.0.0.1:5173", "http://localhost:5173",
]
_allowed_origins = list(load_settings().cors_origins)
if "*" in _allowed_origins and os.environ.get("ENV") != "production":
    _allowed_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（前端）
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
frontend_v2_dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-v2", "dist")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
if os.path.exists(frontend_v2_dist_dir):
    app.mount("/preview", StaticFiles(directory=frontend_v2_dist_dir, html=True), name="frontend-v2-preview")


# ============ 首页 ============
@app.get("/")
async def root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "IT资产全生命周期管理系统"}


# ============ 认证接口（无需登录） ============
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账户已被禁用，请联系管理员")

    user.last_login = datetime.now()
    db.commit()

    token = create_access_token({"sub": str(user.id), "username": user.username})
    user_resp = _build_user_response(user)
    return LoginResponse(token=token, user=user_resp)


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return _build_user_response(current_user)


@app.put("/api/auth/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改当前用户密码"""
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@app.get("/api/auth/permissions", response_model=PermissionConfig)
async def get_permission_config():
    """获取权限配置（权限定义和分组）"""
    return PermissionConfig(
        groups=[PermissionGroup(name=g["name"], permissions=g["permissions"]) for g in PERMISSION_GROUPS],
        definitions=PERMISSION_DEFINITIONS
    )


# ============ 用户管理 CRUD ============
@app.get("/api/users", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:view"))
):
    query = db.query(User)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            User.username.ilike(search_pattern),
            User.real_name.ilike(search_pattern),
            User.department.ilike(search_pattern),
        ))
    if status:
        query = query.filter(User.status == status)

    total = query.count()
    items = query.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()

    result = [_build_user_response(u) for u in items]
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@app.post("/api/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:create"))
):
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"用户名 {data.username} 已存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        email=data.email,
        phone=data.phone,
        department=data.department,
    )
    if data.role_ids:
        roles = db.query(Role).filter(Role.id.in_(data.role_ids)).all()
        user.roles = roles

    db.add(user)
    db.flush()
    _audit_create(db, current_user, "user", str(user.id), data.model_dump())
    db.commit()
    db.refresh(user)
    return _build_user_response(user)


@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:edit"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = data.model_dump(exclude_unset=True)
    previous = {
        key: "[REDACTED]"
        if key == "password"
        else [role.id for role in user.roles]
        if key == "role_ids"
        else getattr(user, key)
        for key in update_data
    }

    if data.real_name is not None:
        user.real_name = data.real_name
    if data.email is not None:
        user.email = data.email
    if data.phone is not None:
        user.phone = data.phone
    if data.department is not None:
        user.department = data.department
    if data.status is not None:
        user.status = data.status
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role_ids is not None:
        roles = db.query(Role).filter(Role.id.in_(data.role_ids)).all()
        user.roles = roles

    user.updated_at = datetime.now()
    _audit_update(db, current_user, "user", str(user.id), previous, update_data)
    db.commit()
    db.refresh(user)
    return _build_user_response(user)


@app.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:delete"))
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    admin_role = db.query(Role).filter(Role.code == "admin").first()
    if admin_role and admin_role in user.roles:
        admin_count = db.query(User).filter(User.roles.contains(admin_role), User.status == "active").count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="系统至少需要保留一个活跃管理员账号")

    previous = {"status": user.status}
    user.status = "disabled"
    _audit_update(
        db, current_user, "user", str(user.id), previous, {"status": user.status}
    )
    db.commit()
    return {"message": "用户已禁用"}


@app.post("/api/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:edit"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    import secrets as _secrets
    pwd = data.new_password or _secrets.token_urlsafe(12)
    user.password_hash = hash_password(pwd)
    _audit_update(
        db,
        current_user,
        "user",
        str(user.id),
        {"password": "[REDACTED]"},
        {"password": "[REDACTED]"},
    )
    db.commit()
    if data.new_password is None:
        return {"message": "密码已自动生成并重置，请通过安全渠道通知用户", "generated": True}
    return {"message": "密码已重置成功", "generated": False}


# ============ 角色管理 CRUD ============
@app.get("/api/users/by-role/{role_code}")
async def list_users_by_role(
    role_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """按角色获取用户列表（用于审批人选择等场景）"""
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        raise HTTPException(404, f"角色 {role_code} 不存在")
    users = [u for u in role.users if u.status == "active"]
    return [{"id": u.id, "real_name": u.real_name, "username": u.username, "department": u.department} for u in users]


@app.get("/api/roles", response_model=dict)
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:view"))
):
    items = db.query(Role).order_by(Role.id).all()
    result = []
    for r in items:
        perms = json.loads(r.permissions) if r.permissions else []
        result.append(RoleResponse(
            id=r.id, name=r.name, code=r.code,
            description=r.description, permissions=perms,
            is_system=r.is_system,
            user_count=len(r.users),
            created_at=r.created_at
        ))
    return {"total": len(result), "items": result}


@app.post("/api/roles", response_model=RoleResponse)
async def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:create"))
):
    existing = db.query(Role).filter(Role.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"角色编码 {data.code} 已存在")

    role = Role(
        name=data.name,
        code=data.code,
        description=data.description,
        permissions=json.dumps(data.permissions, ensure_ascii=False),
    )
    db.add(role)
    db.flush()
    _audit_create(db, current_user, "role", str(role.id), data.model_dump())
    db.commit()
    db.refresh(role)
    return RoleResponse(
        id=role.id, name=role.name, code=role.code,
        description=role.description, permissions=data.permissions,
        is_system=False, user_count=0, created_at=role.created_at
    )


@app.put("/api/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:edit"))
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(role, key) for key in update_data}

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = json.dumps(data.permissions, ensure_ascii=False)

    role.updated_at = datetime.now()
    _audit_update(db, current_user, "role", str(role.id), previous, update_data)
    db.commit()
    db.refresh(role)
    perms = json.loads(role.permissions) if role.permissions else []
    return RoleResponse(
        id=role.id, name=role.name, code=role.code,
        description=role.description, permissions=perms,
        is_system=role.is_system, user_count=len(role.users),
        created_at=role.created_at
    )


@app.delete("/api/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:delete"))
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可删除")

    if len(role.users) > 0:
        raise HTTPException(status_code=400, detail="该角色下还有用户，不可删除")

    _audit_delete(
        db,
        current_user,
        "role",
        str(role.id),
        {"code": role.code, "name": role.name},
    )
    db.delete(role)
    db.commit()
    return {"message": "删除成功"}


def _build_user_response(user: User) -> UserResponse:
    """构造用户响应对象"""
    roles = [RoleBrief(id=r.id, name=r.name, code=r.code) for r in user.roles]
    perms = get_user_permissions(user)
    return UserResponse(
        id=user.id, username=user.username,
        real_name=user.real_name, email=user.email,
        phone=user.phone, department=user.department,
        status=user.status, last_login=user.last_login,
        created_at=user.created_at, roles=roles, permissions=perms
    )


# ============ 下拉选项配置 ============
@app.get("/api/config/dropdowns", response_model=DropdownConfig)
async def get_dropdown_config(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """聚合 dictionaries(enabled) + categories(enabled) 返回 21 字段 DropdownConfig（结构零变更，A-07）。"""
    data = {}
    for field, (source, key) in DROPDOWN_FIELD_TO_SOURCE.items():
        if source == "constants":
            data[field] = LIFECYCLE_STAGES
        elif source == "category":
            rows = db.query(Category.category_name).filter(
                Category.enabled == True
            ).order_by(Category.sort_order, Category.id).all()
            data[field] = [r[0] for r in rows]
        else:  # source == "dict"
            rows = db.query(Dictionary.value).filter(
                Dictionary.group_code == key, Dictionary.enabled == True
            ).order_by(Dictionary.sort_order, Dictionary.id).all()
            data[field] = [r[0] for r in rows]
    return DropdownConfig(**data)


# ============ 搜索选项（各字段去重值） ============
@app.get("/api/distinct-values")
async def get_distinct_values(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """从所有表中提取可搜索字段的去重值，供前端 filterable select 使用"""
    def distinct(model, field_name):
        col = getattr(model, field_name)
        vals = db.query(col).filter(col != None, col != '').distinct().order_by(col).all()
        return [v[0] for v in vals if v[0]]

    # 资产主表字段
    brands = distinct(Asset, 'brand')
    models = distinct(Asset, 'model')
    rooms = distinct(Asset, 'room')
    cabinets = distinct(Asset, 'cabinet')
    u_positions = distinct(Asset, 'u_position')
    device_names = distinct(Asset, 'device_name')
    project_names = distinct(Asset, 'project_name')
    departments = distinct(Asset, 'department')
    ownerships = distinct(Asset, 'ownership')
    sn_list = distinct(Asset, 'sn')
    responsible_persons = distinct(Asset, 'responsible_person')
    config_summaries = distinct(Asset, 'config_summary')
    contract_nos_asset = distinct(Asset, 'contract_no')
    vendor_contacts = distinct(Asset, 'vendor_contact')

    # 用户表字段
    user_departments = distinct(User, 'department')
    user_names = [u.real_name for u in db.query(User).filter(User.status == 'active', User.real_name != None, User.real_name != '').all()]

    # 子表字段
    request_nos = distinct(Procurement, 'request_no')
    vendors = distinct(Procurement, 'vendor')
    procurement_device_names = distinct(Procurement, 'device_name')
    applicants = distinct(Procurement, 'applicant')

    work_order_nos = distinct(Change, 'work_order_no')
    approvers_change = distinct(Change, 'approver')
    executors = distinct(Change, 'executor')

    fault_nos = distinct(Fault, 'fault_no')
    repair_persons = distinct(Fault, 'repair_person')
    parts_replaced = distinct(Fault, 'parts_replaced')

    warranty_nos = distinct(Warranty, 'warranty_no')
    warranty_types = distinct(Warranty, 'warranty_type')
    warranty_vendors = distinct(Warranty, 'warranty_vendor')
    contract_nos_warr = distinct(Warranty, 'contract_no')
    decision_persons = distinct(Warranty, 'decision_person')
    renewal_contract_nos = distinct(Warranty, 'renewal_contract_no')

    approvers_retire = distinct(Retirement, 'approver')
    application_nos = distinct(Retirement, 'application_no')
    uninstall_persons = distinct(Retirement, 'uninstall_person')
    data_clear_persons = distinct(Retirement, 'data_clear_person')
    disposal_methods = distinct(Retirement, 'disposal_method')

    # 移入表字段
    inbound_nos = distinct(AssetInbound, 'inbound_no')
    receivers = distinct(AssetInbound, 'receiver')

    # 移出表字段
    outbound_nos = distinct(AssetOutbound, 'outbound_no')
    operators = distinct(AssetOutbound, 'operator')
    outbound_approvers = distinct(AssetOutbound, 'approver')

    # 合同编号合并（资产主表 + 维保 + 续保）
    contract_nos = sorted(set(contract_nos_asset + contract_nos_warr + renewal_contract_nos))

    # 部门合并（资产 + 用户）
    all_departments = sorted(set(departments + user_departments))

    # 审批人合并（变更 + 退役 + 移出 + 系统用户）
    all_approvers = sorted(set(approvers_change + approvers_retire + outbound_approvers + user_names))

    # 执行人（变更 + 系统用户）
    all_executors = sorted(set(executors + user_names))

    # 维修人（故障 + 系统用户）
    all_repair_persons = sorted(set(repair_persons + user_names))

    # 决策人（维保 + 系统用户）
    all_decision_persons = sorted(set(decision_persons + user_names))

    # 下架人/清除人（退役 + 系统用户）
    all_uninstall_persons = sorted(set(uninstall_persons + user_names))
    all_data_clear_persons = sorted(set(data_clear_persons + user_names))

    # 人员名合并（系统用户 + 资产责任人 + 所有子表人名字段）
    all_persons = sorted(set(
        responsible_persons + receivers + operators + all_approvers + all_executors +
        all_repair_persons + all_decision_persons + all_uninstall_persons + all_data_clear_persons + user_names
    ))

    return {
        "brands": brands,
        "models": models,
        "rooms": rooms,
        "cabinets": cabinets,
        "u_positions": u_positions,
        "device_names": sorted(set(device_names + procurement_device_names)),
        "project_names": project_names,
        "departments": all_departments,
        "ownerships": ownerships,
        "vendor_contacts": vendor_contacts,
        "sn_list": sn_list,
        "persons": all_persons,
        "suppliers": vendors,
        "contract_nos": contract_nos,
        "request_nos": request_nos,
        "approvers": all_approvers,
        "executors": all_executors,
        "repair_persons": all_repair_persons,
        "decision_persons": all_decision_persons,
        "uninstall_persons": all_uninstall_persons,
        "data_clear_persons": all_data_clear_persons,
        "disposal_methods": disposal_methods,
        "application_nos": application_nos,
        "parts_replaced": parts_replaced,
        "warranty_nos": warranty_nos,
        "warranty_types": warranty_types,
        "warranty_vendors": warranty_vendors,
    }


# ============ 资产台账主索引 CRUD ============
@app.get("/api/assets", response_model=dict)
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    stage: Optional[str] = None,
    warranty_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("assets:view"))
):
    query = db.query(Asset)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            Asset.asset_code.ilike(search_pattern),
            Asset.brand.ilike(search_pattern),
            Asset.model.ilike(search_pattern),
            Asset.sn.ilike(search_pattern),
            Asset.room.ilike(search_pattern),
            Asset.cabinet.ilike(search_pattern),
            Asset.u_position.ilike(search_pattern),
            Asset.device_name.ilike(search_pattern),
            Asset.project_name.ilike(search_pattern),
            Asset.department.ilike(search_pattern),
            Asset.ownership.ilike(search_pattern),
            Asset.responsible_person.ilike(search_pattern),
            Asset.contract_no.ilike(search_pattern),
            Asset.config_summary.ilike(search_pattern),
        ))
    if category:
        query = query.filter(Asset.asset_category == category)
    if stage:
        query = query.filter(Asset.lifecycle_stage == stage)
    if warranty_status:
        query = query.filter(Asset.warranty_status == warranty_status)

    total = query.count()
    items = query.order_by(Asset.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 附加维保告警信息
    today = date.today()
    result = []
    for a in items:
        d = AssetResponse.model_validate(a).model_dump()
        if a.warranty_expire_date:
            if a.warranty_expire_date < today and a.lifecycle_stage in ACTIVE_STAGES:
                d["warranty_alert"] = "expired"
            elif a.warranty_expire_date < today + timedelta(days=30) and a.lifecycle_stage in ACTIVE_STAGES:
                d["warranty_alert"] = "expiring_soon"
            else:
                d["warranty_alert"] = "normal"
        else:
            d["warranty_alert"] = "none"
        result.append(d)

    return {"total": total, "page": page, "page_size": page_size, "items": result}


@app.get("/api/assets/{asset_code}", response_model=AssetResponse)
async def get_asset(asset_code: str, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:view"))):
    asset = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@app.post("/api/assets", response_model=AssetResponse)
async def create_asset(data: AssetCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:create"))):
    # 检查编号唯一性
    existing = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 已存在")
    # BUG-003 修复：检查SN唯一性
    if data.sn:
        existing_sn = db.query(Asset).filter(Asset.sn == data.sn).first()
        if existing_sn:
            raise HTTPException(status_code=400, detail=f"SN序列号 {data.sn} 已被资产 {existing_sn.asset_code} 使用")
    asset = Asset(**data.model_dump())
    db.add(asset)
    db.flush()
    _audit_create(db, current_user, "asset", asset.asset_code, data.model_dump())
    db.commit()
    db.refresh(asset)
    return asset


@app.put("/api/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:edit"))):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # BUG-003 修复：更新时也检查SN唯一性
    if data.sn and data.sn != asset.sn:
        existing_sn = db.query(Asset).filter(Asset.sn == data.sn).first()
        if existing_sn:
            raise HTTPException(status_code=400, detail=f"SN序列号 {data.sn} 已被资产 {existing_sn.asset_code} 使用")

    # 如果要修改阶段，检查阶段门禁
    if data.lifecycle_stage and data.lifecycle_stage != asset.lifecycle_stage:
        gate_result = check_stage_gate(db, asset.asset_code, data.lifecycle_stage)
        if not gate_result["allowed"]:
            raise HTTPException(status_code=400, detail=gate_result["message"])

    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(asset, key) for key in update_data}
    for key, value in update_data.items():
        setattr(asset, key, value)
    asset.last_updated = datetime.now()
    _audit_update(db, current_user, "asset", asset.asset_code, previous, update_data)
    db.commit()
    db.refresh(asset)
    return asset


@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:delete"))):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    # 先删除关联子表记录（含移入移出）
    for Model in [Procurement, Change, Fault, Warranty, Retirement, AssetInbound, AssetOutbound]:
        db.query(Model).filter(Model.asset_code == asset.asset_code).delete()
    # 删除审批工作流关联记录（通知→步骤→审批单，顺序重要）
    approval_reqs = db.query(ApprovalRequest).filter(ApprovalRequest.asset_code == asset.asset_code).all()
    for apr in approval_reqs:
        db.query(ApprovalNotification).filter(ApprovalNotification.request_id == apr.id).delete()
        db.query(ApprovalStep).filter(ApprovalStep.request_id == apr.id).delete()
        db.delete(apr)
    _audit_delete(
        db,
        current_user,
        "asset",
        asset.asset_code,
        {"asset_category": asset.asset_category, "sn": asset.sn},
    )
    db.delete(asset)
    db.commit()
    return {"message": "删除成功"}


# ============ 阶段门禁检查 ============
@app.get("/api/assets/{asset_code}/stage-gate/{target_stage}")
async def get_stage_gate(asset_code: str, target_stage: str, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:view"))):
    return check_stage_gate(db, asset_code, target_stage)


# ============ 采购入库 CRUD（重构） ============
@app.get("/api/procurements", response_model=dict)
async def list_procurements(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("procurement:view"))
):
    query = db.query(Procurement)
    if asset_code:
        query = query.filter(Procurement.asset_code == asset_code)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            Procurement.asset_code.ilike(search_pattern),
            Procurement.request_no.ilike(search_pattern),
            Procurement.vendor.ilike(search_pattern),
            Procurement.device_name.ilike(search_pattern),
            Procurement.applicant.ilike(search_pattern),
        ))
    total = query.count()
    items = query.order_by(Procurement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [ProcurementResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/procurements", response_model=ProcurementResponse)
async def create_procurement(data: ProcurementCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("procurement:create"))):
    # asset_code为Optional，仅在提供时校验
    if data.asset_code:
        asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
        if not asset:
            raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    # 自动计算总价
    if data.quantity and data.unit_price and not data.total_price:
        data.total_price = data.quantity * data.unit_price
    item = Procurement(**data.model_dump())
    db.add(item)
    db.flush()
    _audit_create(db, current_user, "procurement", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/procurements/{item_id}", response_model=ProcurementResponse)
async def update_procurement(item_id: int, data: ProcurementUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("procurement:edit"))):
    item = db.query(Procurement).filter(Procurement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 如果变更了asset_code，需校验
    if data.asset_code and data.asset_code != item.asset_code:
        asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
        if not asset:
            raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    # 自动计算总价
    if item.quantity and item.unit_price:
        item.total_price = item.quantity * item.unit_price
    _audit_update(db, current_user, "procurement", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/procurements/{item_id}")
async def delete_procurement(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("procurement:delete"))):
    item = db.query(Procurement).filter(Procurement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    _audit_delete(
        db, current_user, "procurement", str(item.id), {"asset_code": item.asset_code}
    )
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 资产移入 CRUD（新增） ============
@app.get("/api/asset-inbound", response_model=dict)
async def list_asset_inbound(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, search: Optional[str] = None,
    inspection_result: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inbound:view"))
):
    """移入记录列表（分页+筛选+搜索）"""
    query = db.query(AssetInbound)
    if asset_code:
        query = query.filter(AssetInbound.asset_code == asset_code)
    if inspection_result:
        query = query.filter(AssetInbound.inspection_result == inspection_result)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            AssetInbound.inbound_no.ilike(search_pattern),
            AssetInbound.asset_category.ilike(search_pattern),
            AssetInbound.brand.ilike(search_pattern),
            AssetInbound.model.ilike(search_pattern),
            AssetInbound.sn.ilike(search_pattern),
            AssetInbound.receiver.ilike(search_pattern),
            AssetInbound.project_name.ilike(search_pattern),
        ))
    total = query.count()
    items = query.order_by(AssetInbound.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [InboundResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/asset-inbound", response_model=InboundResponse)
async def create_asset_inbound(data: InboundCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("inbound:create"))):
    """创建移入记录 — 验收合格→自动创建Asset"""
    # 如果提供了asset_code，校验存在性
    if data.asset_code:
        asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
        if not asset:
            raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    item = AssetInbound(**data.model_dump())
    db.add(item)
    db.flush()

    # DEF-P1-001 修复：创建时如果验收结果为"合格"，也触发自动创建Asset联动
    if item.inspection_result == "合格" and not item.asset_code:
        cat = db.query(Category).filter(
            Category.category_name == (item.asset_category or "其他"), Category.enabled == True
        ).first()
        cat_code = cat.category_code if cat else "OTH"
        prefix = f"DC-CL-{cat_code}-"
        max_code = db.query(func.max(Asset.asset_code)).filter(
            Asset.asset_code.like(f"{prefix}%")
        ).first()
        if max_code and max_code[0]:
            seq_match = re.search(r'(\d+)$', max_code[0])
            seq = int(seq_match.group(1)) + 1 if seq_match else 1
        else:
            seq = 1
        generated_code = f"{prefix}{seq:03d}"

        new_asset = Asset(
            asset_code=generated_code,
            asset_category=item.asset_category or "其他",
            brand=item.brand,
            model=item.model,
            sn=item.sn,
            lifecycle_stage="上架",
            entry_date=item.inbound_date,
            responsible_person=item.receiver,
            remarks=f"移入验收合格自动创建（移入记录ID:{item.id}）",
        )
        db.add(new_asset)
        # P2 前向日志：资产建档（出生）起点 —— 规划→上架，使阶段时间线有起点
        record_stage_change(
            db, generated_code, "规划", "上架",
            datetime.combine(item.inbound_date or date.today(), time.min),
            operator=current_user.real_name or current_user.username,
            reason="资产建档", is_backfill=False
        )
        item.asset_code = generated_code

    _audit_create(db, current_user, "asset_inbound", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/asset-inbound/{id}", response_model=InboundResponse)
async def update_asset_inbound(id: int, data: InboundUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("inbound:edit"))):
    """更新移入记录 — 验收合格→自动创建Asset"""
    item = db.query(AssetInbound).filter(AssetInbound.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="移入记录不存在")

    # 检查是否inspection_result从非"合格"变为"合格"
    old_inspection = item.inspection_result
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)

    new_inspection = item.inspection_result
    # 当验收结果从非"合格"变为"合格"时，自动创建Asset记录
    if new_inspection == "合格" and (old_inspection != "合格" or old_inspection is None):
        # 如果asset_code为空，自动生成
        if not item.asset_code:
            # 生成asset_code格式 DC-CL-[分类码]-[序号]
            cat = db.query(Category).filter(
                Category.category_name == (item.asset_category or "其他"), Category.enabled == True
            ).first()
            cat_code = cat.category_code if cat else "OTH"
            # 查询当日该分类最大序号
            prefix = f"DC-CL-{cat_code}-"
            max_code = db.query(func.max(Asset.asset_code)).filter(
                Asset.asset_code.like(f"{prefix}%")
            ).first()
            if max_code and max_code[0]:
                seq_match = re.search(r'(\d+)$', max_code[0])
                seq = int(seq_match.group(1)) + 1 if seq_match else 1
            else:
                seq = 1
            generated_code = f"{prefix}{seq:03d}"

            # 创建Asset记录（按模板字段映射）
            # storage_location格式如"5-4-R03-15U"，尝试解析为room/cabinet/u_position
            parsed_loc = parse_location(item.storage_location or "")
            new_asset = Asset(
                asset_code=generated_code,
                asset_category=item.asset_category or "其他",
                asset_category_2=None,
                brand=item.brand,
                model=item.model,
                sn=item.sn,
                lifecycle_stage="上架",
                entry_date=item.inbound_date,
                responsible_person=item.receiver,
                room=parsed_loc.get("room"),
                cabinet=parsed_loc.get("cabinet"),
                u_position=parsed_loc.get("u_position"),
                warranty_status=None,
                warranty_expire_date=None,
                remarks=f"移入验收合格自动创建（移入记录ID:{id}）",
            )
            db.add(new_asset)
            db.flush()
            # P2 前向日志：资产建档（出生）起点 —— 规划→上架，使阶段时间线有起点
            record_stage_change(
                db, generated_code, "规划", "上架",
                datetime.combine(item.inbound_date or date.today(), time.min),
                operator=current_user.real_name or current_user.username,
                reason="资产建档", is_backfill=False
            )

            # 将生成的asset_code回填到AssetInbound记录
            item.asset_code = generated_code

    item.updated_at = datetime.now()
    _audit_update(db, current_user, "asset_inbound", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/asset-inbound/{id}")
async def delete_asset_inbound(id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("inbound:delete"))):
    """删除移入记录"""
    item = db.query(AssetInbound).filter(AssetInbound.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="移入记录不存在")
    _audit_delete(
        db,
        current_user,
        "asset_inbound",
        str(item.id),
        {"asset_code": item.asset_code, "inbound_no": item.inbound_no},
    )
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 资产移出 CRUD（新增） ============
@app.get("/api/asset-outbound", response_model=dict)
async def list_asset_outbound(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, search: Optional[str] = None,
    outbound_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("outbound:view"))
):
    """移出记录列表（分页+筛选+搜索）"""
    query = db.query(AssetOutbound)
    if asset_code:
        query = query.filter(AssetOutbound.asset_code == asset_code)
    if outbound_category:
        query = query.filter(AssetOutbound.outbound_category == outbound_category)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            AssetOutbound.outbound_no.ilike(search_pattern),
            AssetOutbound.asset_code.ilike(search_pattern),
            AssetOutbound.destination.ilike(search_pattern),
            AssetOutbound.operator.ilike(search_pattern),
        ))
    total = query.count()
    items = query.order_by(AssetOutbound.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [OutboundResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/asset-outbound", response_model=OutboundResponse)
async def create_asset_outbound(data: OutboundCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("outbound:create"))):
    """创建移出记录 — 报废类别→自动创建Retirement+审批流"""
    # 校验资产编号存在性（移出必须关联已有资产）
    asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if not asset:
        raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")

    item = AssetOutbound(**data.model_dump())
    db.add(item)
    db.flush()

    # 当移出类别为"报废"时，自动创建Retirement记录和审批流
    if data.outbound_category == "报废":
        # 自动创建Retirement记录
        retirement = Retirement(
            asset_code=data.asset_code,
            retire_reason=data.outbound_reason or "移出报废",
            retire_category="报废",
            uninstall_date=data.outbound_date,
            uninstall_person=data.operator,
            approver=data.approver,
            remarks=f"移出报废自动创建（移出记录ID:{item.id}）",
        )
        db.add(retirement)
        db.flush()

        # 自动提交retirement_approval审批流
        auto_result = outbound_retirement_auto_submit(
            db, data.asset_code, retirement.id, current_user.id,
            data.outbound_reason or "移出报废"
        )
        if auto_result and auto_result.get("request_no"):
            if item.remarks:
                item.remarks += f"\n[自动审批单: {auto_result['request_no']}]"
            else:
                item.remarks = f"[自动审批单: {auto_result['request_no']}]"

    _audit_create(db, current_user, "asset_outbound", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/asset-outbound/{id}", response_model=OutboundResponse)
async def update_asset_outbound(id: int, data: OutboundUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("outbound:edit"))):
    """更新移出记录"""
    item = db.query(AssetOutbound).filter(AssetOutbound.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="移出记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    item.updated_at = datetime.now()
    _audit_update(db, current_user, "asset_outbound", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/asset-outbound/{id}")
async def delete_asset_outbound(id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("outbound:delete"))):
    """删除移出记录"""
    item = db.query(AssetOutbound).filter(AssetOutbound.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="移出记录不存在")
    _audit_delete(
        db,
        current_user,
        "asset_outbound",
        str(item.id),
        {"asset_code": item.asset_code, "outbound_no": item.outbound_no},
    )
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 变更迁移 CRUD（字段替换） ============
@app.get("/api/changes", response_model=dict)
async def list_changes(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("change:view"))
):
    query = db.query(Change)
    if asset_code:
        query = query.filter(Change.asset_code == asset_code)
    total = query.count()
    items = query.order_by(Change.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [ChangeResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/changes", response_model=ChangeResponse)
async def create_change(data: ChangeCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("change:create"))):
    # 校验资产编号存在性
    asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if not asset:
        raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    if asset.lifecycle_stage == "已报废":
        raise HTTPException(status_code=400, detail="已报废资产不允许创建变更记录")
    item = Change(**data.model_dump())
    db.add(item)
    db.flush()
    _audit_create(db, current_user, "change", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/changes/{item_id}", response_model=ChangeResponse)
async def update_change(item_id: int, data: ChangeUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("change:edit"))):
    item = db.query(Change).filter(Change.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    _audit_update(db, current_user, "change", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/changes/{item_id}")
async def delete_change(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("change:delete"))):
    item = db.query(Change).filter(Change.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    _audit_delete(db, current_user, "change", str(item.id), {"asset_code": item.asset_code})
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 故障维修 CRUD（+2字段，P2→P2-严重） ============
@app.get("/api/faults", response_model=dict)
async def list_faults(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fault:view"))
):
    query = db.query(Fault)
    if asset_code:
        query = query.filter(Fault.asset_code == asset_code)
    total = query.count()
    items = query.order_by(Fault.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [FaultResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/faults", response_model=FaultResponse)
async def create_fault(data: FaultCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("fault:create"))):
    # 校验资产编号存在性
    asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if not asset:
        raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    if asset.lifecycle_stage == "已报废":
        raise HTTPException(status_code=400, detail="已报废资产不允许创建故障记录")
    item = Fault(**data.model_dump())
    db.add(item)
    db.flush()
    # P1/P2-严重故障降级流程（P2-严重替代原P2）
    if data.fault_level in ["P1", "P2-严重"] and asset.lifecycle_stage in ["上架", "运行", "在途"]:
        original_stage = asset.lifecycle_stage
        asset.lifecycle_stage = "维修"
        # P2 前向日志：写一条「原阶段→维修」，由 create_fault 唯一负责（故障降级审批路径 drive_stage_change 会跳过，避免双写/空转）
        record_stage_change(
            db, asset.asset_code, original_stage, "维修",
            datetime.now(timezone.utc), operator=current_user.real_name or current_user.username,
            reason=f"P{data.fault_level}故障自动降级 故障单{item.id}", is_backfill=False
        )
        auto_result = auto_submit_fault_approval(db, asset.asset_code, item.id, data.fault_level, current_user.id, original_stage)
        if auto_result and auto_result.get("request_no"):
            approval_note = f"\n[自动审批单: {auto_result['request_no']}]"
            if item.remarks:
                item.remarks += approval_note
            else:
                item.remarks = approval_note
    _audit_create(db, current_user, "fault", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/faults/{item_id}", response_model=FaultResponse)
async def update_fault(item_id: int, data: FaultUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("fault:edit"))):
    item = db.query(Fault).filter(Fault.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    _audit_update(db, current_user, "fault", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/faults/{item_id}")
async def delete_fault(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("fault:delete"))):
    item = db.query(Fault).filter(Fault.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    _audit_delete(db, current_user, "fault", str(item.id), {"asset_code": item.asset_code})
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 维保续保 CRUD（+3字段） ============
@app.get("/api/warranties", response_model=dict)
async def list_warranties(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warranty:view"))
):
    query = db.query(Warranty)
    if asset_code:
        query = query.filter(Warranty.asset_code == asset_code)
    total = query.count()
    items = query.order_by(Warranty.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [WarrantyResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/warranties", response_model=WarrantyResponse)
async def create_warranty(data: WarrantyCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("warranty:create"))):
    # 校验资产编号存在性
    asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if not asset:
        raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    if asset.lifecycle_stage == "已报废":
        raise HTTPException(status_code=400, detail="已报废资产不允许创建维保记录")
    item = Warranty(**data.model_dump())
    db.add(item)
    db.flush()
    _audit_create(db, current_user, "warranty", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/warranties/{item_id}", response_model=WarrantyResponse)
async def update_warranty(item_id: int, data: WarrantyUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("warranty:edit"))):
    item = db.query(Warranty).filter(Warranty.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    _audit_update(db, current_user, "warranty", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/warranties/{item_id}")
async def delete_warranty(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("warranty:delete"))):
    item = db.query(Warranty).filter(Warranty.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    _audit_delete(db, current_user, "warranty", str(item.id), {"asset_code": item.asset_code})
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 退役报废 CRUD（枚举变更） ============
@app.get("/api/retirements", response_model=dict)
async def list_retirements(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("retirement:view"))
):
    query = db.query(Retirement)
    if asset_code:
        query = query.filter(Retirement.asset_code == asset_code)
    total = query.count()
    items = query.order_by(Retirement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [RetirementResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/retirements", response_model=RetirementResponse)
async def create_retirement(data: RetirementCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("retirement:create"))):
    # 校验资产编号存在性
    asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if not asset:
        raise HTTPException(status_code=400, detail=f"资产编号 {data.asset_code} 不存在")
    if asset.lifecycle_stage == "已报废":
        existing_ret = db.query(Retirement).filter(Retirement.asset_code == data.asset_code).first()
        if existing_ret:
            raise HTTPException(status_code=400, detail="已报废资产已有退役记录，不允许重复创建")
    item = Retirement(**data.model_dump())
    db.add(item)
    db.flush()
    _audit_create(db, current_user, "retirement", str(item.id), data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/retirements/{item_id}", response_model=RetirementResponse)
async def update_retirement(item_id: int, data: RetirementUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("retirement:edit"))):
    item = db.query(Retirement).filter(Retirement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    previous = {key: getattr(item, key) for key in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    _audit_update(db, current_user, "retirement", str(item.id), previous, update_data)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/retirements/{item_id}")
async def delete_retirement(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("retirement:delete"))):
    item = db.query(Retirement).filter(Retirement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    _audit_delete(db, current_user, "retirement", str(item.id), {"asset_code": item.asset_code})
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 校验仪表盘 ============
@app.get("/api/validation", response_model=ValidationDashboard)
async def get_validation_dashboard(db: Session = Depends(get_db), current_user: User = Depends(require_permission("validation:view"))):
    return run_all_checks(db)


# ============ 统计概览 ============
@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_permission("dashboard:view"))):
    from sqlalchemy import func as sqlfunc
    today = date.today()

    total = db.query(Asset).count()
    by_stage = dict(db.query(Asset.lifecycle_stage, sqlfunc.count(Asset.id)).group_by(Asset.lifecycle_stage).all())
    by_category = dict(db.query(Asset.asset_category, sqlfunc.count(Asset.id)).group_by(Asset.asset_category).all())

    warranty_expired = db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage.in_(ACTIVE_STAGES)
    ).count()
    warranty_soon = db.query(Asset).filter(
        Asset.warranty_expire_date.between(today, today + timedelta(days=30)),
        Asset.lifecycle_stage.in_(ACTIVE_STAGES)
    ).count()
    # P1/P2-严重统计（P2-严重替代原P2）
    p1_p2_open = db.query(Fault).filter(Fault.fault_level.in_(["P1", "P2-严重"]), Fault.recovery_date == None).count()

    return {
        "total_assets": total,
        "by_stage": by_stage,
        "by_category": by_category,
        "warranty_expired": warranty_expired,
        "warranty_expiring_soon": warranty_soon,
        "p1_p2_unresolved": p1_p2_open
    }


# ============ 资产生命周期时间线 ============
@app.get("/api/assets/{asset_code}/timeline")
async def get_asset_timeline(asset_code: str, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:view"))):
    asset = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    timeline = []
    # 采购事件
    for p in db.query(Procurement).filter(Procurement.asset_code == asset_code).all():
        timeline.append({"stage": "采购入库", "date": str(p.request_date or ""), "detail": f"采购单号:{p.request_no or '-'} 供应商:{p.vendor or '-'}"})
    # 移入事件
    for ib in db.query(AssetInbound).filter(AssetInbound.asset_code == asset_code).all():
        timeline.append({"stage": "资产移入", "date": str(ib.inbound_date or ""), "detail": f"移入单号:{ib.inbound_no or '-'} 接收类型:{ib.receive_type or '-'} 验收:{ib.inspection_result or '-'}"})
    # 变更事件
    for c in db.query(Change).filter(Change.asset_code == asset_code).all():
        timeline.append({"stage": "变更迁移", "date": str(c.execute_date or ""), "detail": f"类型:{c.change_type} 工单:{c.work_order_no or '-'}"})
    # 故障事件
    for f in db.query(Fault).filter(Fault.asset_code == asset_code).all():
        timeline.append({"stage": "故障维修", "date": str(f.fault_date or ""), "detail": f"{f.fault_level} {f.fault_description or ''}"})
    # 维保事件
    for w in db.query(Warranty).filter(Warranty.asset_code == asset_code).all():
        timeline.append({"stage": "维保续保", "date": str(w.end_date or ""), "detail": f"合同:{w.contract_no or '-'} 类型:{w.warranty_type or '-'} 决策:{w.renewal_decision or '-'}"})
    # 退役事件
    for r in db.query(Retirement).filter(Retirement.asset_code == asset_code).all():
        timeline.append({"stage": "退役报废", "date": str(r.uninstall_date or r.approval_date or ""), "detail": f"类别:{r.retire_category or '-'} 处置:{r.disposal_method or '-'}"})
    # 移出事件
    for ob in db.query(AssetOutbound).filter(AssetOutbound.asset_code == asset_code).all():
        timeline.append({"stage": "资产移出", "date": str(ob.outbound_date or ""), "detail": f"移出单号:{ob.outbound_no or '-'} 类别:{ob.outbound_category or '-'} 去向:{ob.destination or '-'}"})

    timeline.sort(key=lambda x: x["date"] or "9999", reverse=True)
    return {"asset_code": asset_code, "current_stage": asset.lifecycle_stage, "timeline": timeline}


# ============ 批量导入 ============
@app.post("/api/import/assets")
async def api_import_assets(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(require_permission("import_export:import"))):
    """批量导入资产台账（Excel文件上传）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持xlsx/xls格式文件")
    result = await import_assets_excel(file, db)
    record_audit(
        db,
        current_user.id,
        "import",
        "import",
        "assets",
        {"result": result},
    )
    db.commit()
    return result


@app.post("/api/import/{table_type}")
async def api_import_subtable(table_type: str, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(require_permission("import_export:import"))):
    """批量导入分表数据"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持xlsx/xls格式文件")
    result = await import_subtable_excel(file, table_type, db)
    record_audit(
        db,
        current_user.id,
        "import",
        "import",
        table_type,
        {"result": result},
    )
    db.commit()
    return result


# ============ 批量导出 ============
@app.get("/api/export/assets")
async def api_export_assets(
    category: Optional[str] = None, stage: Optional[str] = None,
    warranty_status: Optional[str] = None, search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("import_export:export"))
):
    """导出资产台账为Excel文件"""
    return export_assets_excel(db, category, stage, warranty_status, search)


@app.get("/api/export/{table_type}")
async def api_export_subtable(table_type: str, db: Session = Depends(get_db), current_user: User = Depends(require_permission("import_export:export"))):
    """导出分表为Excel文件"""
    return export_subtable_excel(db, table_type)


# ============ 导入模板下载 ============
@app.get("/api/template/{table_type}")
async def api_download_template(table_type: str, current_user: User = Depends(require_permission("import_export:import"))):
    """下载导入模板"""
    return download_import_template(table_type)


# ============ 报表统计 ============
@app.get("/api/reports/comprehensive")
async def api_comprehensive_report(db: Session = Depends(get_db), current_user: User = Depends(require_permission("reports:view"))):
    """综合报表：资产概览+分类+阶段+维保+故障+年龄+变更"""
    return get_comprehensive_report(db)


@app.get("/api/reports/warranty-expiry")
async def api_warranty_expiry_report(days: int = Query(90, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(require_permission("reports:view"))):
    """维保到期报表：已过期+即将到期"""
    return get_warranty_expiry_report(db, days)


@app.get("/api/reports/fault-analysis")
async def api_fault_analysis_report(
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports:view"))
):
    """故障分析报表：故障频率/根因/P级分布"""
    return get_fault_analysis_report(db, start_date, end_date)


@app.get("/api/reports/change-frequency")
async def api_change_frequency_report(db: Session = Depends(get_db), current_user: User = Depends(require_permission("reports:view"))):
    """变更频率报表"""
    return get_change_frequency_report(db)


# ============ 统计看板（报表统计模块新增，前缀 /api/stats/*） ============
# 与既有 GET /api/stats（dashboard:view）路径不冲突；本路由统一使用 reports:view
app.include_router(stats_router)
# 系统配置模块 P0：字典/分类配置 API（前缀 /api/config）
app.include_router(config_router)
app.include_router(health_router)


# ============ 审批工作流辅助函数 ============
def _build_approval_response(request: ApprovalRequest, db: Session) -> ApprovalRequestResponse:
    """构造审批单响应对象"""
    applicant = db.query(User).filter(User.id == request.applicant_id).first()
    applicant_name = applicant.real_name or applicant.username if applicant else None

    steps = db.query(ApprovalStep).filter(ApprovalStep.request_id == request.id).order_by(ApprovalStep.level).all()
    step_responses = []
    for s in steps:
        approver = db.query(User).filter(User.id == s.approver_id).first() if s.approver_id else None
        step_responses.append(ApprovalStepResponse(
            id=s.id, level=s.level, approver_id=s.approver_id,
            approver_role=s.approver_role,
            approver_name=approver.real_name or approver.username if approver else None,
            status=s.status, comment=s.comment, acted_at=s.acted_at
        ))

    try:
        attachments = json.loads(request.attachments) if request.attachments else []
    except (json.JSONDecodeError, TypeError):
        attachments = []

    return ApprovalRequestResponse(
        id=request.id, request_no=request.request_no,
        approval_type=request.approval_type,
        approval_type_name=APPROVAL_TYPE_NAMES.get(request.approval_type, request.approval_type),
        asset_code=request.asset_code, current_stage=request.current_stage,
        target_stage=request.target_stage, reason=request.reason,
        attachments=attachments, status=request.status,
        applicant_id=request.applicant_id, applicant_name=applicant_name,
        applied_at=request.applied_at, current_level=request.current_level,
        rejection_count=request.rejection_count, approved_at=request.approved_at,
        created_at=request.created_at, updated_at=request.updated_at,
        steps=step_responses
    )


# ============ 审批工作流API ============

@app.post("/api/approval-requests")
async def create_approval_request(data: ApprovalRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:submit"))):
    """创建审批单(draft)"""
    asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
    if not asset:
        raise HTTPException(400, f"资产编号 {data.asset_code} 不存在")
    engine = WorkflowEngine(db)
    try:
        engine.validate_stage(data.approval_type, asset)
    except ValueError as e:
        raise HTTPException(400, str(e))

    request_no = generate_request_no(db)
    current_stage = asset.lifecycle_stage
    target_stage = engine.get_target_stage(data.approval_type, current_stage)

    request = ApprovalRequest(
        request_no=request_no,
        approval_type=data.approval_type,
        asset_code=data.asset_code,
        current_stage=current_stage,
        target_stage=target_stage,
        reason=data.reason,
        attachments=json.dumps(data.attachments, ensure_ascii=False) if data.attachments else "[]",
        status="draft",
        applicant_id=current_user.id,
    )
    db.add(request)
    db.flush()
    _audit_create(
        db,
        current_user,
        "approval_request",
        str(request.id),
        data.model_dump(),
    )
    db.commit()
    db.refresh(request)

    return _build_approval_response(request, db)


@app.post("/api/approval-requests/{request_id}/submit")
async def submit_approval_request(request_id: int, data: ApprovalSubmitRequest = None, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:submit"))):
    """提交审批 draft→pending"""
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(404, "审批单不存在")
    if req.applicant_id != current_user.id:
        raise HTTPException(403, "仅申请人可提交审批单")
    try:
        approver_ids = data.approver_ids if data else None
        result = submit_approval(db, request_id, approver_ids)
        return _build_approval_response(result, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/approval-requests/{request_id}/action")
async def approval_action(request_id: int, data: ApprovalActionRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:approve"))):
    """审批操作(approve/reject)"""
    try:
        result = process_approval_action(db, request_id, data.action, data.comment, current_user.id)
        return _build_approval_response(result, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/approval-requests/{request_id}/cancel")
async def cancel_approval_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:submit"))):
    """撤回审批"""
    try:
        result = cancel_approval(db, request_id, current_user.id)
        return _build_approval_response(result, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/approval-requests/{request_id}/resubmit")
async def resubmit_approval_request(request_id: int, data: ApprovalRequestResubmit, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:submit"))):
    """驳回后重新提交"""
    try:
        result = resubmit_approval(db, request_id, data.reason, data.attachments)
        return _build_approval_response(result, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/approval-requests/stats", response_model=ApprovalStatsResponse)
async def approval_stats(db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """审批统计"""
    total_pending = db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending").count()
    my_pending_steps = db.query(ApprovalStep).filter(
        ApprovalStep.approver_id == current_user.id, ApprovalStep.status == "pending"
    ).count()
    role_codes = get_user_role_codes(current_user)
    if "admin" in role_codes:
        my_pending_steps = total_pending
    my_applications = db.query(ApprovalRequest).filter(ApprovalRequest.applicant_id == current_user.id).count()
    unread = db.query(ApprovalNotification).filter(
        ApprovalNotification.user_id == current_user.id, ApprovalNotification.is_read == False
    ).count()
    by_type = dict(db.query(ApprovalRequest.approval_type, func.count(ApprovalRequest.id)).filter(
        ApprovalRequest.status == "pending"
    ).group_by(ApprovalRequest.approval_type).all())
    return ApprovalStatsResponse(
        total_pending=total_pending, my_pending=my_pending_steps,
        my_applications=my_applications, unread_notifications=unread, by_type=by_type
    )


@app.get("/api/approval-requests/my-pending")
async def my_pending_approvals(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:approve"))
):
    """我的待审列表"""
    pending_steps = db.query(ApprovalStep).filter(
        ApprovalStep.approver_id == current_user.id,
        ApprovalStep.status == "pending"
    ).all()
    request_ids = [s.request_id for s in pending_steps]
    role_codes = get_user_role_codes(current_user)
    if "admin" in role_codes:
        all_pending_steps = db.query(ApprovalStep).filter(ApprovalStep.status == "pending").all()
        request_ids = [s.request_id for s in all_pending_steps]

    if not request_ids:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    query = db.query(ApprovalRequest).filter(
        ApprovalRequest.id.in_(request_ids),
        ApprovalRequest.status == "pending"
    )
    total = query.count()
    items = query.order_by(ApprovalRequest.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    result = [_build_approval_response(r, db) for r in items]
    return {"total": total, "page": page, "page_size": page_size, "items": [r.model_dump() for r in result]}


@app.get("/api/approval-requests/my-applications")
async def my_applications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))
):
    """我的申请列表"""
    query = db.query(ApprovalRequest).filter(ApprovalRequest.applicant_id == current_user.id)
    total = query.count()
    items = query.order_by(ApprovalRequest.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    result = [_build_approval_response(r, db) for r in items]
    return {"total": total, "page": page, "page_size": page_size, "items": [r.model_dump() for r in result]}


@app.get("/api/approval-requests")
async def list_approval_requests(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    approval_type: Optional[str] = None, status: Optional[str] = None,
    asset_code: Optional[str] = None, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("approval:view"))
):
    """审批单列表"""
    query = db.query(ApprovalRequest)
    if approval_type:
        query = query.filter(ApprovalRequest.approval_type == approval_type)
    if status:
        query = query.filter(ApprovalRequest.status == status)
    if asset_code:
        query = query.filter(ApprovalRequest.asset_code.ilike(f"%{asset_code}%"))
    total = query.count()
    items = query.order_by(ApprovalRequest.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    result = [_build_approval_response(r, db) for r in items]
    return {"total": total, "page": page, "page_size": page_size, "items": [r.model_dump() for r in result]}


@app.get("/api/approval-requests/{request_id}")
async def get_approval_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """审批单详情"""
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(404, "审批单不存在")
    return _build_approval_response(req, db)


@app.get("/api/approval-requests/by-asset/{asset_code}")
async def approval_by_asset(asset_code: str, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """按资产查询审批历史"""
    items = db.query(ApprovalRequest).filter(ApprovalRequest.asset_code == asset_code).order_by(ApprovalRequest.id.desc()).all()
    result = [_build_approval_response(r, db) for r in items]
    return {"total": len(result), "items": [r.model_dump() for r in result]}


@app.get("/api/approval-config/types")
async def approval_type_config(db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """审批类型配置（数据源：workflow_templates 表，契约不变）"""
    engine = WorkflowEngine(db)
    configs = []
    for t in engine.list_templates():
        configs.append(ApprovalTypeConfigItem(
            type_code=t.approval_type, type_name=t.approval_type_name,
            current_stage=t.current_stage, target_stage=t.target_stage,
            mode=t.mode, chain=t.chain if t.chain is not None else []
        ))
    return {"types": [c.model_dump() for c in configs]}


@app.get("/api/approval-config/dropdowns", response_model=ApprovalDropdownConfig)
async def approval_dropdown_config(current_user: User = Depends(require_permission("approval:view"))):
    """审批下拉选项"""
    types = [{"code": t, "name": APPROVAL_TYPE_NAMES.get(t, t)} for t in APPROVAL_TYPES]
    status_name_map = {"draft": "草稿", "pending": "待审批", "approved": "已通过", "rejected": "已驳回", "cancelled": "已撤回"}
    statuses = [{"code": s, "name": status_name_map.get(s, s)} for s in APPROVAL_STATUSES]
    return ApprovalDropdownConfig(approval_types=types, approval_statuses=statuses)


# ============ 审批模板管理 API（仅 admin: approval_template:manage） ============
class WorkflowTemplateUpdate(BaseModel):
    """审批模板更新体（仅白名单字段，approval_type 锁定不可改）"""
    current_stage: Optional[str] = None
    target_stage: Optional[str] = None
    mode: Optional[str] = None
    chain: Optional[list] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None


def _serialize_template(t: WorkflowTemplate) -> dict:
    """将 WorkflowTemplate 序列化为 API 响应 dict"""
    return {
        "id": t.id,
        "approval_type": t.approval_type,
        "approval_type_name": t.approval_type_name,
        "current_stage": t.current_stage,
        "target_stage": t.target_stage,
        "mode": t.mode,
        "chain": t.chain if t.chain is not None else [],
        "enabled": t.enabled,
        "remark": t.remark,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@app.get("/api/approval-templates")
async def list_workflow_templates(db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval_template:manage"))):
    """审批模板列表（仅管理员）"""
    engine = WorkflowEngine(db)
    return {"templates": [_serialize_template(t) for t in engine.list_templates()]}


@app.get("/api/approval-templates/{template_id}")
async def get_workflow_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval_template:manage"))):
    """审批模板详情（仅管理员）"""
    engine = WorkflowEngine(db)
    t = engine.get_template_by_id(template_id)
    if not t:
        raise HTTPException(404, "审批模板不存在")
    return _serialize_template(t)


@app.put("/api/approval-templates/{template_id}")
async def update_workflow_template(template_id: int, data: WorkflowTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval_template:manage"))):
    """更新审批模板（仅管理员，approval_type 锁定不可改）"""
    engine = WorkflowEngine(db)
    template = engine.get_template_by_id(template_id)
    previous = None
    if template:
        previous = {
            "current_stage": template.current_stage,
            "target_stage": template.target_stage,
            "mode": template.mode,
            "chain": template.chain,
            "enabled": template.enabled,
            "remark": template.remark,
        }
    update_data = data.model_dump(exclude_unset=True)
    try:
        t = engine.update_template(template_id, update_data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit_update(
        db,
        current_user,
        "approval_template",
        str(t.id),
        previous or {},
        update_data,
    )
    db.commit()
    return _serialize_template(t)


@app.get("/api/approval-notifications")
async def list_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))
):
    """通知列表"""
    query = db.query(ApprovalNotification).filter(ApprovalNotification.user_id == current_user.id)
    total = query.count()
    items = query.order_by(ApprovalNotification.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    result = []
    for n in items:
        r = ApprovalNotificationResponse.model_validate(n).model_dump()
        req = db.query(ApprovalRequest).filter(ApprovalRequest.id == n.request_id).first()
        if req:
            r["request_no"] = req.request_no
        result.append(r)
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@app.put("/api/approval-notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """标记通知已读"""
    n = db.query(ApprovalNotification).filter(ApprovalNotification.id == notification_id, ApprovalNotification.user_id == current_user.id).first()
    if not n:
        raise HTTPException(404, "通知不存在")
    n.is_read = True
    db.commit()
    return {"message": "已标记已读"}


@app.put("/api/approval-notifications/read-all")
async def mark_all_notifications_read(db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """批量标记所有通知已读"""
    db.query(ApprovalNotification).filter(
        ApprovalNotification.user_id == current_user.id, ApprovalNotification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "已标记全部已读"}


@app.get("/api/approval-notifications/unread-count")
async def unread_notification_count(db: Session = Depends(get_db), current_user: User = Depends(require_permission("approval:view"))):
    """未读通知数量"""
    count = db.query(ApprovalNotification).filter(
        ApprovalNotification.user_id == current_user.id, ApprovalNotification.is_read == False
    ).count()
    return {"unread_count": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
