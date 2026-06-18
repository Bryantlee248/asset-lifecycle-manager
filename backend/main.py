"""FastAPI主应用 - IT资产全生命周期管理系统"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import date, datetime, timedelta
import json
import os

from database import get_db, Asset, Procurement, Change, Fault, Warranty, Retirement, User, Role, AuditLog
from auth import (
    hash_password, verify_password, create_access_token, get_current_user,
    get_current_user_optional, get_user_permissions, get_user_role_codes,
    require_permission, require_any_permission,
    init_default_data, PERMISSION_DEFINITIONS, PERMISSION_GROUPS
)
from import_export_reports import (
    import_assets_excel, import_subtable_excel,
    export_assets_excel, export_subtable_excel, download_import_template,
    get_comprehensive_report, get_warranty_expiry_report,
    get_fault_analysis_report, get_change_frequency_report
)
from schemas import (
    AssetCreate, AssetUpdate, AssetResponse,
    ProcurementCreate, ProcurementUpdate, ProcurementResponse,
    ChangeCreate, ChangeUpdate, ChangeResponse,
    FaultCreate, FaultUpdate, FaultResponse,
    WarrantyCreate, WarrantyUpdate, WarrantyResponse,
    RetirementCreate, RetirementUpdate, RetirementResponse,
    ValidationDashboard, DropdownConfig, StageGateResult,
    LoginRequest, LoginResponse, ChangePasswordRequest, ResetPasswordRequest,
    UserCreate, UserUpdate, UserResponse,
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionGroup, PermissionInfo, PermissionConfig,
    RoleBrief
)
from validation import run_all_checks, check_stage_gate
from constants import (
    CATEGORIES, LIFECYCLE_STAGES, WARRANTY_STATUSES, INSPECTION_RESULTS,
    CHANGE_TYPES, FAULT_LEVELS, HANDLE_METHODS, ROOT_CAUSES,
    RENEWAL_DECISIONS, RETIRE_CATEGORIES, DATA_CLEAR_OPTIONS, COMPLETION_STATUSES
)


# ============ Lifespan ============
@asynccontextmanager
async def lifespan(app):
    db = next(get_db())
    try:
        init_default_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="IT资产全生命周期管理系统", version="2.0.0", lifespan=lifespan)

# CORS支持 - 限制来源
_allowed_origins = os.environ.get("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（前端）
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


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

    # 更新最后登录时间
    user.last_login = datetime.now()
    db.commit()

    # 生成Token
    token = create_access_token({"sub": str(user.id), "username": user.username})

    # 构造用户响应
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
    # 检查用户名唯一性
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
    # 分配角色
    if data.role_ids:
        roles = db.query(Role).filter(Role.id.in_(data.role_ids)).all()
        user.roles = roles

    db.add(user)
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
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否是系统管理员且是唯一的admin
    admin_role = db.query(Role).filter(Role.code == "admin").first()
    if admin_role and admin_role in user.roles:
        admin_count = db.query(User).filter(User.roles.contains(admin_role)).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="系统至少需要保留一个管理员账号")

    db.delete(user)
    db.commit()
    return {"message": "删除成功"}


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
    db.commit()
    return {"message": f"密码已重置为: {pwd}", "generated": data.new_password is None}


# ============ 角色管理 CRUD ============
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

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = json.dumps(data.permissions, ensure_ascii=False)

    role.updated_at = datetime.now()
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
async def get_dropdown_config(current_user: User = Depends(get_current_user)):
    return DropdownConfig(
        categories=CATEGORIES,
        lifecycle_stages=LIFECYCLE_STAGES,
        warranty_statuses=WARRANTY_STATUSES,
        inspection_results=INSPECTION_RESULTS,
        change_types=CHANGE_TYPES,
        fault_levels=FAULT_LEVELS,
        handle_methods=HANDLE_METHODS,
        root_causes=ROOT_CAUSES,
        renewal_decisions=RENEWAL_DECISIONS,
        retire_categories=RETIRE_CATEGORIES,
        data_clear_options=DATA_CLEAR_OPTIONS,
        completion_statuses=COMPLETION_STATUSES,
    )


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
            Asset.location.ilike(search_pattern),
            Asset.responsible_person.ilike(search_pattern),
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
            if a.warranty_expire_date < today and a.lifecycle_stage in ["上架", "运行", "维修"]:
                d["warranty_alert"] = "expired"
            elif a.warranty_expire_date < today + timedelta(days=30) and a.lifecycle_stage in ["上架", "运行", "维修"]:
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
    asset = Asset(**data.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@app.put("/api/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:edit"))):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # 如果要修改阶段，检查阶段门禁
    if data.lifecycle_stage and data.lifecycle_stage != asset.lifecycle_stage:
        gate_result = check_stage_gate(db, asset.asset_code, data.lifecycle_stage)
        if not gate_result["allowed"]:
            raise HTTPException(status_code=400, detail=gate_result["message"])

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(asset, key, value)
    asset.last_updated = datetime.now()
    db.commit()
    db.refresh(asset)
    return asset


@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("assets:delete"))):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    # 先删除关联子表记录
    for Model in [Procurement, Change, Fault, Warranty, Retirement]:
        db.query(Model).filter(Model.asset_code == asset.asset_code).delete()
    # 记录审计日志
    audit_log = AuditLog(
        user_id=current_user.id,
        action="delete",
        resource_type="asset",
        resource_id=asset.asset_code,
        detail=f"删除资产: {asset.asset_code} ({asset.asset_category})"
    )
    db.add(audit_log)
    db.delete(asset)
    db.commit()
    return {"message": "删除成功"}


# ============ 阶段门禁检查 ============
@app.get("/api/assets/{asset_code}/stage-gate/{target_stage}")
async def get_stage_gate(asset_code: str, target_stage: str, db: Session = Depends(get_db)):
    return check_stage_gate(db, asset_code, target_stage)


# ============ 采购入库 CRUD ============
@app.get("/api/procurements", response_model=dict)
async def list_procurements(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    asset_code: Optional[str] = None, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("procurement:view"))
):
    query = db.query(Procurement)
    if asset_code:
        query = query.filter(Procurement.asset_code == asset_code)
    total = query.count()
    items = query.order_by(Procurement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [ProcurementResponse.model_validate(i).model_dump() for i in items]}


@app.post("/api/procurements", response_model=ProcurementResponse)
async def create_procurement(data: ProcurementCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("procurement:create"))):
    # 自动计算总价
    if data.quantity and data.unit_price and not data.total_price:
        data.total_price = data.quantity * data.unit_price
    item = Procurement(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/procurements/{item_id}", response_model=ProcurementResponse)
async def update_procurement(item_id: int, data: ProcurementUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("procurement:edit"))):
    item = db.query(Procurement).filter(Procurement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    # 自动计算总价
    if item.quantity and item.unit_price:
        item.total_price = item.quantity * item.unit_price
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/procurements/{item_id}")
async def delete_procurement(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("procurement:delete"))):
    item = db.query(Procurement).filter(Procurement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 变更迁移 CRUD ============
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
    item = Change(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/changes/{item_id}", response_model=ChangeResponse)
async def update_change(item_id: int, data: ChangeUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("change:edit"))):
    item = db.query(Change).filter(Change.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/changes/{item_id}")
async def delete_change(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("change:delete"))):
    item = db.query(Change).filter(Change.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 故障维修 CRUD ============
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
    item = Fault(**data.model_dump())
    db.add(item)
    # 如果是P1/P2故障，自动将主表阶段设为"维修"
    if data.fault_level in ["P1", "P2"]:
        asset = db.query(Asset).filter(Asset.asset_code == data.asset_code).first()
        if asset and asset.lifecycle_stage in ["运行", "上架"]:
            asset.lifecycle_stage = "维修"
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/faults/{item_id}", response_model=FaultResponse)
async def update_fault(item_id: int, data: FaultUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("fault:edit"))):
    item = db.query(Fault).filter(Fault.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/faults/{item_id}")
async def delete_fault(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("fault:delete"))):
    item = db.query(Fault).filter(Fault.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 维保续保 CRUD ============
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
    item = Warranty(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/warranties/{item_id}", response_model=WarrantyResponse)
async def update_warranty(item_id: int, data: WarrantyUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("warranty:edit"))):
    item = db.query(Warranty).filter(Warranty.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/warranties/{item_id}")
async def delete_warranty(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("warranty:delete"))):
    item = db.query(Warranty).filter(Warranty.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============ 退役报废 CRUD ============
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
    item = Retirement(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/retirements/{item_id}", response_model=RetirementResponse)
async def update_retirement(item_id: int, data: RetirementUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("retirement:edit"))):
    item = db.query(Retirement).filter(Retirement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/retirements/{item_id}")
async def delete_retirement(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("retirement:delete"))):
    item = db.query(Retirement).filter(Retirement.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
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
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).count()
    warranty_soon = db.query(Asset).filter(
        Asset.warranty_expire_date.between(today, today + timedelta(days=30)),
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).count()
    p1_p2_open = db.query(Fault).filter(Fault.fault_level.in_(["P1", "P2"]), Fault.recovery_date == None).count()

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
        timeline.append({"stage": "采购入库", "date": str(p.arrival_date or p.install_date or ""), "detail": f"采购单号:{p.purchase_order or '-'} 供应商:{p.supplier or '-'}"})
    # 变更事件
    for c in db.query(Change).filter(Change.asset_code == asset_code).all():
        timeline.append({"stage": "变更迁移", "date": str(c.execute_date or ""), "detail": f"类型:{c.change_type} {c.old_location or ''}→{c.new_location or ''}"})
    # 故障事件
    for f in db.query(Fault).filter(Fault.asset_code == asset_code).all():
        timeline.append({"stage": "故障维修", "date": str(f.fault_date or ""), "detail": f"{f.fault_level} {f.fault_description or ''}"})
    # 维保事件
    for w in db.query(Warranty).filter(Warranty.asset_code == asset_code).all():
        timeline.append({"stage": "维保续保", "date": str(w.end_date or ""), "detail": f"合同:{w.contract_no or '-'} 决策:{w.renewal_decision or '-'}"})
    # 退役事件
    for r in db.query(Retirement).filter(Retirement.asset_code == asset_code).all():
        timeline.append({"stage": "退役报废", "date": str(r.uninstall_date or r.approval_date or ""), "detail": f"类别:{r.retire_category or '-'} 处置:{r.disposal_method or '-'}"})

    timeline.sort(key=lambda x: x["date"] or "9999", reverse=True)
    return {"asset_code": asset_code, "current_stage": asset.lifecycle_stage, "timeline": timeline}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ============ 批量导入 ============
@app.post("/api/import/assets")
async def api_import_assets(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(require_permission("import_export:import"))):
    """批量导入资产台账（Excel文件上传）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持xlsx/xls格式文件")
    return await import_assets_excel(file, db)


@app.post("/api/import/{table_type}")
async def api_import_subtable(table_type: str, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(require_permission("import_export:import"))):
    """批量导入分表数据（procurement/change/fault/warranty/retirement）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持xlsx/xls格式文件")
    return await import_subtable_excel(file, table_type, db)


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
async def api_download_template(table_type: str):
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
