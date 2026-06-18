"""Pydantic schemas for request/response validation"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


# ============ 认证 ============
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: "UserResponse"


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, description="原密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class ResetPasswordRequest(BaseModel):
    new_password: Optional[str] = Field(None, min_length=6, description="新密码，为空则自动生成")


# ============ 用户 ============
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    real_name: Optional[str] = Field(None, max_length=50, description="真实姓名")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    department: Optional[str] = Field(None, max_length=50, description="部门")
    role_ids: list[int] = Field(default=[], description="角色ID列表")


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    role_ids: Optional[list[int]] = None
    password: Optional[str] = Field(None, min_length=6, description="重置密码")


class RoleBrief(BaseModel):
    id: int
    name: str
    code: str
    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    status: str = "active"
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    roles: list[RoleBrief] = []
    permissions: list[str] = []

    class Config:
        from_attributes = True


# ============ 角色 ============
class RoleCreate(BaseModel):
    name: str = Field(..., max_length=50, description="角色名称")
    code: str = Field(..., max_length=50, description="角色编码")
    description: Optional[str] = Field(None, max_length=200, description="角色描述")
    permissions: list[str] = Field(default=[], description="权限列表")


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list[str]] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    permissions: list[str] = []
    is_system: bool = False
    user_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 权限配置 ============
class PermissionGroup(BaseModel):
    name: str
    permissions: list[str]


class PermissionInfo(BaseModel):
    code: str
    name: str


class PermissionConfig(BaseModel):
    groups: list[PermissionGroup]
    definitions: dict[str, str]


# ============ 资产台账主索引 ============
class AssetBase(BaseModel):
    asset_code: str = Field(..., max_length=30, description="资产编号")
    asset_category: str = Field(..., max_length=20, description="资产分类")
    brand: Optional[str] = Field(None, max_length=50, description="品牌")
    model: Optional[str] = Field(None, max_length=100, description="型号")
    sn: Optional[str] = Field(None, max_length=50, description="SN序列号")
    location: Optional[str] = Field(None, max_length=30, description="位置")
    lifecycle_stage: str = Field("规划", max_length=20, description="生命周期阶段")
    entry_date: Optional[date] = Field(None, description="入场日期")
    responsible_person: Optional[str] = Field(None, max_length=30, description="责任人")
    warranty_status: Optional[str] = Field(None, max_length=20, description="维保状态")
    warranty_expire_date: Optional[date] = Field(None, description="维保到期日")
    ip_address: Optional[str] = Field(None, max_length=50, description="IP地址")
    remarks: Optional[str] = Field(None, description="备注")


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    sn: Optional[str] = None
    location: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    entry_date: Optional[date] = None
    responsible_person: Optional[str] = None
    warranty_status: Optional[str] = None
    warranty_expire_date: Optional[date] = None
    ip_address: Optional[str] = None
    remarks: Optional[str] = None


class AssetResponse(AssetBase):
    id: int
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 采购入库 ============
class ProcurementBase(BaseModel):
    asset_code: str
    purchase_order: Optional[str] = None
    contract_no: Optional[str] = None
    supplier: Optional[str] = None
    quantity: Optional[int] = 1
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    arrival_date: Optional[date] = None
    inspector: Optional[str] = None
    inspection_result: Optional[str] = None
    install_date: Optional[date] = None
    remarks: Optional[str] = None


class ProcurementCreate(ProcurementBase):
    pass


class ProcurementUpdate(BaseModel):
    purchase_order: Optional[str] = None
    contract_no: Optional[str] = None
    supplier: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    arrival_date: Optional[date] = None
    inspector: Optional[str] = None
    inspection_result: Optional[str] = None
    install_date: Optional[date] = None
    remarks: Optional[str] = None


class ProcurementResponse(ProcurementBase):
    id: int
    class Config:
        from_attributes = True


# ============ 变更迁移 ============
class ChangeBase(BaseModel):
    asset_code: str
    change_type: str
    old_location: Optional[str] = None
    new_location: Optional[str] = None
    old_ip: Optional[str] = None
    new_ip: Optional[str] = None
    old_responsible: Optional[str] = None
    new_responsible: Optional[str] = None
    change_reason: Optional[str] = None
    approver: Optional[str] = None
    executor: Optional[str] = None
    execute_date: Optional[date] = None
    completion_status: Optional[str] = "进行中"
    remarks: Optional[str] = None


class ChangeCreate(ChangeBase):
    pass


class ChangeUpdate(BaseModel):
    change_type: Optional[str] = None
    old_location: Optional[str] = None
    new_location: Optional[str] = None
    old_ip: Optional[str] = None
    new_ip: Optional[str] = None
    old_responsible: Optional[str] = None
    new_responsible: Optional[str] = None
    change_reason: Optional[str] = None
    approver: Optional[str] = None
    executor: Optional[str] = None
    execute_date: Optional[date] = None
    completion_status: Optional[str] = None
    remarks: Optional[str] = None


class ChangeResponse(ChangeBase):
    id: int
    class Config:
        from_attributes = True


# ============ 故障维修 ============
class FaultBase(BaseModel):
    asset_code: str
    fault_level: str
    fault_description: Optional[str] = None
    fault_date: Optional[date] = None
    repair_person: Optional[str] = None
    handle_method: Optional[str] = None
    parts_replaced: Optional[str] = None
    root_cause: Optional[str] = None
    recovery_date: Optional[date] = None
    downtime_hours: Optional[float] = None
    is_recurring: Optional[bool] = False
    remarks: Optional[str] = None


class FaultCreate(FaultBase):
    pass


class FaultUpdate(BaseModel):
    fault_level: Optional[str] = None
    fault_description: Optional[str] = None
    fault_date: Optional[date] = None
    repair_person: Optional[str] = None
    handle_method: Optional[str] = None
    parts_replaced: Optional[str] = None
    root_cause: Optional[str] = None
    recovery_date: Optional[date] = None
    downtime_hours: Optional[float] = None
    is_recurring: Optional[bool] = None
    remarks: Optional[str] = None


class FaultResponse(FaultBase):
    id: int
    class Config:
        from_attributes = True


# ============ 维保续保 ============
class WarrantyBase(BaseModel):
    asset_code: str
    contract_no: Optional[str] = None
    coverage: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    renewal_decision: Optional[str] = None
    decision_person: Optional[str] = None
    decision_date: Optional[date] = None
    renewal_contract_no: Optional[str] = None
    renewal_start_date: Optional[date] = None
    renewal_end_date: Optional[date] = None
    cost: Optional[float] = None
    remarks: Optional[str] = None


class WarrantyCreate(WarrantyBase):
    pass


class WarrantyUpdate(BaseModel):
    contract_no: Optional[str] = None
    coverage: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    renewal_decision: Optional[str] = None
    decision_person: Optional[str] = None
    decision_date: Optional[date] = None
    renewal_contract_no: Optional[str] = None
    renewal_start_date: Optional[date] = None
    renewal_end_date: Optional[date] = None
    cost: Optional[float] = None
    remarks: Optional[str] = None


class WarrantyResponse(WarrantyBase):
    id: int
    class Config:
        from_attributes = True


# ============ 退役报废 ============
class RetirementBase(BaseModel):
    asset_code: str
    retire_reason: Optional[str] = None
    retire_category: Optional[str] = None
    application_no: Optional[str] = None
    approver: Optional[str] = None
    approval_date: Optional[date] = None
    uninstall_date: Optional[date] = None
    uninstall_person: Optional[str] = None
    data_cleared: Optional[str] = None
    data_clear_person: Optional[str] = None
    disposal_method: Optional[str] = None
    residual_value: Optional[float] = None
    remarks: Optional[str] = None


class RetirementCreate(RetirementBase):
    pass


class RetirementUpdate(BaseModel):
    retire_reason: Optional[str] = None
    retire_category: Optional[str] = None
    application_no: Optional[str] = None
    approver: Optional[str] = None
    approval_date: Optional[date] = None
    uninstall_date: Optional[date] = None
    uninstall_person: Optional[str] = None
    data_cleared: Optional[str] = None
    data_clear_person: Optional[str] = None
    disposal_method: Optional[str] = None
    residual_value: Optional[float] = None
    remarks: Optional[str] = None


class RetirementResponse(RetirementBase):
    id: int
    class Config:
        from_attributes = True


# ============ 校验结果 ============
class ValidationItem(BaseModel):
    check_name: str
    description: str
    count: int
    severity: str  # "error" | "warning"
    details: list[str] = []


class ValidationDashboard(BaseModel):
    total_assets: int
    total_errors: int
    total_warnings: int
    checks: list[ValidationItem]


# ============ 下拉选项配置 ============
class DropdownConfig(BaseModel):
    categories: list[str]
    lifecycle_stages: list[str]
    warranty_statuses: list[str]
    inspection_results: list[str]
    change_types: list[str]
    fault_levels: list[str]
    handle_methods: list[str]
    root_causes: list[str]
    renewal_decisions: list[str]
    retire_categories: list[str]
    data_clear_options: list[str]
    completion_statuses: list[str]


# ============ 阶段门禁 ============
class StageGateResult(BaseModel):
    allowed: bool
    message: str