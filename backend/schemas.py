"""Pydantic schemas for request/response validation — 新台账模板v1.0"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime


# ============ 枚举校验（运行期查 DB/缓存） ============
# 仅保留 lifecycle_stage 硬编码（O4）；其余枚举统一经 config_cache.is_valid_enum 校验（A-08）。
from config_cache import is_valid_enum, get_enum_values

_VALID_LIFECYCLE_STAGES = ["规划", "在途", "上架", "运行", "维修", "待报废", "已报废"]


# ============ 认证 ============
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    # BUG-009 修复：移除密码 min_length 限制
    # 短密码不应返回422(Pydantic格式错误)，应统一由业务逻辑返回401(认证失败)
    password: str = Field(..., max_length=100, description="密码")


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


# ============ 资产台账主索引（新台账模板v1.0 — 34列） ============
class AssetBase(BaseModel):
    # — 保留字段 —
    asset_code: str = Field(..., max_length=30, description="资产编号")
    asset_category: str = Field(..., max_length=20, description="资产分类（第一类）")
    brand: Optional[str] = Field(None, max_length=50, description="品牌")
    model: Optional[str] = Field(None, max_length=100, description="型号")
    sn: Optional[str] = Field(None, max_length=50, description="SN序列号")
    lifecycle_stage: str = Field("规划", max_length=20, description="生命周期阶段")
    entry_date: Optional[date] = Field(None, description="入场日期")
    responsible_person: Optional[str] = Field(None, max_length=30, description="责任人")
    warranty_status: Optional[str] = Field(None, max_length=20, description="维保状态")
    warranty_expire_date: Optional[date] = Field(None, description="维保到期日")
    remarks: Optional[str] = Field(None, description="备注")
    # — 新增23字段（全部Optional） —
    asset_category_2: Optional[str] = Field(None, max_length=50, description="资产分类（第二类）")
    room: Optional[str] = Field(None, max_length=50, description="所在机房")
    cabinet: Optional[str] = Field(None, max_length=20, description="所在机柜")
    u_position: Optional[str] = Field(None, max_length=20, description="所在U位")
    device_name: Optional[str] = Field(None, max_length=100, description="设备名称")
    project_name: Optional[str] = Field(None, max_length=100, description="项目名称")
    project_no: Optional[str] = Field(None, max_length=50, description="项目序号")
    size: Optional[str] = Field(None, max_length=20, description="尺寸")
    power_consumption: Optional[int] = Field(None, description="设备功耗(W)")
    ownership: Optional[str] = Field(None, max_length=20, description="产权归属")
    department: Optional[str] = Field(None, max_length=50, description="所属部门")
    contract_no: Optional[str] = Field(None, max_length=50, description="合同编号")
    config_summary: Optional[str] = Field(None, description="配置参数摘要")
    integrator_warranty_years: Optional[int] = Field(None, description="集成商维保年限")
    integrator_warranty_start: Optional[date] = Field(None, description="集成商维保起始时间")
    integrator_warranty_end: Optional[date] = Field(None, description="集成商维保到期时间")
    integrator_warranty: Optional[str] = Field(None, max_length=10, description="集成商维保（是/否）")
    vendor_warranty_years: Optional[int] = Field(None, description="原厂维保年限")
    vendor_warranty_start: Optional[date] = Field(None, description="原厂维保起始时间")
    vendor_warranty_end: Optional[date] = Field(None, description="原厂维保到期时间")
    vendor_warranty: Optional[str] = Field(None, max_length=10, description="原厂维保（是/否）")
    vendor_contact: Optional[str] = Field(None, max_length=50, description="厂家售后联系人")
    vendor_phone: Optional[str] = Field(None, max_length=30, description="电话")


class AssetCreate(AssetBase):
    # BUG-010 修复：资产编号格式校验（DC-CL-XXX格式）
    @field_validator('asset_code')
    @classmethod
    def validate_asset_code_format(cls, v):
        import re
        pattern = r'^[A-Za-z]{2,4}-[A-Za-z]{2,4}-[\w-]+$'
        if not re.match(pattern, v):
            raise ValueError(f"资产编号格式不正确，应为类似 DC-CL-SVR-001 的格式（前缀-分类码-序号）")
        return v

    # BUG-004 修复：枚举字段校验（A-08：运行期查 DB 缓存）
    @field_validator('asset_category')
    @classmethod
    def validate_category(cls, v):
        if v is not None and not is_valid_enum("category", v):
            raise ValueError(f"资产分类必须是系统配置中已启用的分类之一: {get_enum_values('category')}")
        return v

    @field_validator('lifecycle_stage')
    @classmethod
    def validate_stage(cls, v):
        if v not in _VALID_LIFECYCLE_STAGES:
            raise ValueError(f"生命周期阶段必须是以下之一: {_VALID_LIFECYCLE_STAGES}")
        return v

    @field_validator('warranty_status')
    @classmethod
    def validate_warranty_status(cls, v):
        if v is not None and not is_valid_enum("warranty_status", v):
            raise ValueError(f"维保状态必须是系统配置中已启用的选项之一: {get_enum_values('warranty_status')}")
        return v

    @field_validator('ownership')
    @classmethod
    def validate_ownership(cls, v):
        if v is not None and not is_valid_enum("ownership_type", v):
            raise ValueError(f"产权归属必须是系统配置中已启用的选项之一: {get_enum_values('ownership_type')}")
        return v


class AssetUpdate(BaseModel):
    # — 保留字段（可选） —
    asset_category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    sn: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    entry_date: Optional[date] = None
    responsible_person: Optional[str] = None
    warranty_status: Optional[str] = None
    warranty_expire_date: Optional[date] = None
    remarks: Optional[str] = None
    # — 新增23可选字段 —
    asset_category_2: Optional[str] = None
    room: Optional[str] = None
    cabinet: Optional[str] = None
    u_position: Optional[str] = None
    device_name: Optional[str] = None
    project_name: Optional[str] = None
    project_no: Optional[str] = None
    size: Optional[str] = None
    power_consumption: Optional[int] = None
    ownership: Optional[str] = None
    department: Optional[str] = None
    contract_no: Optional[str] = None
    config_summary: Optional[str] = None
    integrator_warranty_years: Optional[int] = None
    integrator_warranty_start: Optional[date] = None
    integrator_warranty_end: Optional[date] = None
    integrator_warranty: Optional[str] = None
    vendor_warranty_years: Optional[int] = None
    vendor_warranty_start: Optional[date] = None
    vendor_warranty_end: Optional[date] = None
    vendor_warranty: Optional[str] = None
    vendor_contact: Optional[str] = None
    vendor_phone: Optional[str] = None


class AssetResponse(AssetBase):
    id: int
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 采购入库（重构） ============
class ProcurementBase(BaseModel):
    # — asset_code改为可选（不再强制外键） —
    asset_code: Optional[str] = Field(None, max_length=30, description="关联资产编号（可选）")
    # — 新增字段 —
    request_no: Optional[str] = Field(None, max_length=50, description="采购申请编号")
    vendor: Optional[str] = Field(None, max_length=100, description="供应商/原厂")
    device_name: Optional[str] = Field(None, max_length=100, description="设备名称")
    config_summary: Optional[str] = Field(None, description="配置参数摘要")
    request_date: Optional[date] = Field(None, description="申请日期")
    applicant: Optional[str] = Field(None, max_length=30, description="申请人")
    approval_status: Optional[str] = Field("审批中", max_length=20, description="审批状态")
    # — 保留字段 —
    quantity: Optional[int] = Field(1, description="数量")
    unit_price: Optional[float] = Field(None, description="单价")
    total_price: Optional[float] = Field(None, description="总价")
    remarks: Optional[str] = Field(None, description="备注")


class ProcurementCreate(ProcurementBase):
    @field_validator('approval_status')
    @classmethod
    def validate_approval_status(cls, v):
        if v is not None and not is_valid_enum("procurement_approval_status", v):
            raise ValueError(f"审批状态必须是系统配置中已启用的选项之一: {get_enum_values('procurement_approval_status')}")
        return v


class ProcurementUpdate(BaseModel):
    asset_code: Optional[str] = None
    request_no: Optional[str] = None
    vendor: Optional[str] = None
    device_name: Optional[str] = None
    config_summary: Optional[str] = None
    request_date: Optional[date] = None
    applicant: Optional[str] = None
    approval_status: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    remarks: Optional[str] = None


class ProcurementResponse(ProcurementBase):
    id: int
    class Config:
        from_attributes = True


# ============ 资产移入（新增） ============
class InboundBase(BaseModel):
    asset_code: Optional[str] = Field(None, max_length=30, description="关联资产编号（验收合格后回填）")
    inbound_no: Optional[str] = Field(None, max_length=50, description="移入单号")
    receive_type: Optional[str] = Field(None, max_length=20, description="接收类型")
    ownership: Optional[str] = Field(None, max_length=20, description="产权归属")
    owner_company: Optional[str] = Field(None, max_length=100, description="产权方公司")
    project_name: Optional[str] = Field(None, max_length=100, description="项目名称")
    project_no: Optional[str] = Field(None, max_length=50, description="项目序号")
    asset_category: Optional[str] = Field(None, max_length=20, description="资产分类")
    brand: Optional[str] = Field(None, max_length=50, description="品牌")
    model: Optional[str] = Field(None, max_length=100, description="型号")
    sn: Optional[str] = Field(None, max_length=50, description="SN序列号")
    config_summary: Optional[str] = Field(None, description="配置参数摘要")
    purchase_contract_no: Optional[str] = Field(None, max_length=50, description="采购合同编号")
    purchase_total_price: Optional[float] = Field(None, description="采购总价")
    inbound_date: Optional[date] = Field(None, description="移入日期")
    receiver: Optional[str] = Field(None, max_length=30, description="接收人")
    inspection_result: Optional[str] = Field(None, max_length=20, description="验收结果")
    storage_location: Optional[str] = Field(None, max_length=100, description="存放位置")
    remarks: Optional[str] = Field(None, description="备注")


class InboundCreate(InboundBase):
    @field_validator('receive_type')
    @classmethod
    def validate_receive_type(cls, v):
        if v is not None and not is_valid_enum("receive_type", v):
            raise ValueError(f"接收类型必须是系统配置中已启用的选项之一: {get_enum_values('receive_type')}")
        return v

    @field_validator('ownership')
    @classmethod
    def validate_inbound_ownership(cls, v):
        if v is not None and not is_valid_enum("ownership_type", v):
            raise ValueError(f"产权归属必须是系统配置中已启用的选项之一: {get_enum_values('ownership_type')}")
        return v

    @field_validator('inspection_result')
    @classmethod
    def validate_inspection_result(cls, v):
        if v is not None and not is_valid_enum("inbound_inspection_result", v):
            raise ValueError(f"验收结果必须是系统配置中已启用的选项之一: {get_enum_values('inbound_inspection_result')}")
        return v


class InboundUpdate(BaseModel):
    asset_code: Optional[str] = None
    inbound_no: Optional[str] = None
    receive_type: Optional[str] = None
    ownership: Optional[str] = None
    owner_company: Optional[str] = None
    project_name: Optional[str] = None
    project_no: Optional[str] = None
    asset_category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    sn: Optional[str] = None
    config_summary: Optional[str] = None
    purchase_contract_no: Optional[str] = None
    purchase_total_price: Optional[float] = None
    inbound_date: Optional[date] = None
    receiver: Optional[str] = None
    inspection_result: Optional[str] = None
    storage_location: Optional[str] = None
    remarks: Optional[str] = None


class InboundResponse(InboundBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 资产移出（新增） ============
class OutboundBase(BaseModel):
    asset_code: str = Field(..., max_length=30, description="关联资产编号（移出必须关联已有资产）")
    outbound_no: Optional[str] = Field(None, max_length=50, description="移出单号")
    outbound_reason: Optional[str] = Field(None, description="移出原因")
    outbound_category: Optional[str] = Field(None, max_length=20, description="移出类别")
    destination: Optional[str] = Field(None, max_length=100, description="去向/目的地")
    outbound_date: Optional[date] = Field(None, description="移出日期")
    receiver_contact: Optional[str] = Field(None, max_length=50, description="接收方联系人")
    receiver_phone: Optional[str] = Field(None, max_length=30, description="接收方联系电话")
    operator: Optional[str] = Field(None, max_length=30, description="操作人")
    approver: Optional[str] = Field(None, max_length=30, description="审批人")
    remarks: Optional[str] = Field(None, description="备注")


class OutboundCreate(OutboundBase):
    @field_validator('outbound_category')
    @classmethod
    def validate_outbound_category(cls, v):
        if v is not None and not is_valid_enum("outbound_category", v):
            raise ValueError(f"移出类别必须是系统配置中已启用的选项之一: {get_enum_values('outbound_category')}")
        return v


class OutboundUpdate(BaseModel):
    outbound_no: Optional[str] = None
    outbound_reason: Optional[str] = None
    outbound_category: Optional[str] = None
    destination: Optional[str] = None
    outbound_date: Optional[date] = None
    receiver_contact: Optional[str] = None
    receiver_phone: Optional[str] = None
    operator: Optional[str] = None
    approver: Optional[str] = None
    remarks: Optional[str] = None


class OutboundResponse(OutboundBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 变更迁移（字段替换：+4/-6） ============
class ChangeBase(BaseModel):
    asset_code: str = Field(..., max_length=30, description="关联资产编号")
    change_type: str = Field(..., max_length=20, description="变更类型")
    # — 新增字段 —
    work_order_no: Optional[str] = Field(None, max_length=50, description="工单编号")
    change_content: Optional[str] = Field(None, description="变更内容")
    old_config: Optional[str] = Field(None, description="原配置")
    new_config: Optional[str] = Field(None, description="新配置")
    # — 保留字段 —
    change_reason: Optional[str] = Field(None, description="变更原因")
    approver: Optional[str] = Field(None, max_length=30, description="审批人")
    executor: Optional[str] = Field(None, max_length=30, description="执行人")
    execute_date: Optional[date] = Field(None, description="执行日期")
    completion_status: Optional[str] = Field("进行中", max_length=20, description="完成状态")
    remarks: Optional[str] = Field(None, description="备注")


class ChangeCreate(ChangeBase):
    # BUG-004 修复：变更类型枚举校验
    @field_validator('change_type')
    @classmethod
    def validate_change_type(cls, v):
        if v is not None and not is_valid_enum("change_type", v):
            raise ValueError(f"变更类型必须是系统配置中已启用的选项之一: {get_enum_values('change_type')}")
        return v


class ChangeUpdate(BaseModel):
    change_type: Optional[str] = None
    work_order_no: Optional[str] = None
    change_content: Optional[str] = None
    old_config: Optional[str] = None
    new_config: Optional[str] = None
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


# ============ 故障维修（+2字段） ============
class FaultBase(BaseModel):
    asset_code: str = Field(..., max_length=30, description="关联资产编号")
    fault_level: str = Field(..., max_length=10, description="故障等级")
    fault_description: Optional[str] = Field(None, description="故障现象")
    fault_date: Optional[date] = Field(None, description="故障日期")
    repair_person: Optional[str] = Field(None, max_length=30, description="维修人")
    handle_method: Optional[str] = Field(None, max_length=30, description="处理方式")
    parts_replaced: Optional[str] = Field(None, description="配件更换记录")
    root_cause: Optional[str] = Field(None, max_length=20, description="根因分类")
    recovery_date: Optional[date] = Field(None, description="恢复日期")
    downtime_hours: Optional[float] = Field(None, description="停机时长(小时)")
    is_recurring: Optional[bool] = Field(False, description="是否复发")
    remarks: Optional[str] = Field(None, description="备注")
    # — 新增字段 —
    fault_no: Optional[str] = Field(None, max_length=50, description="故障单号")
    repair_cost: Optional[float] = Field(None, description="维修费用")


class FaultCreate(FaultBase):
    # BUG-004 修复：故障等级枚举校验
    @field_validator('fault_level')
    @classmethod
    def validate_fault_level(cls, v):
        if v is not None and not is_valid_enum("fault_level", v):
            raise ValueError(f"故障等级必须是系统配置中已启用的选项之一: {get_enum_values('fault_level')}")
        return v


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
    fault_no: Optional[str] = None
    repair_cost: Optional[float] = None


class FaultResponse(FaultBase):
    id: int
    class Config:
        from_attributes = True


# ============ 维保续保（+3字段） ============
class WarrantyBase(BaseModel):
    asset_code: str = Field(..., max_length=30, description="关联资产编号")
    contract_no: Optional[str] = Field(None, max_length=50, description="维保合同编号")
    coverage: Optional[str] = Field(None, description="覆盖范围")
    start_date: Optional[date] = Field(None, description="维保起始日")
    end_date: Optional[date] = Field(None, description="维保到期日")
    renewal_decision: Optional[str] = Field(None, max_length=20, description="续保决策")
    decision_person: Optional[str] = Field(None, max_length=30, description="决策人")
    decision_date: Optional[date] = Field(None, description="决策日期")
    renewal_contract_no: Optional[str] = Field(None, max_length=50, description="续保合同编号")
    renewal_start_date: Optional[date] = Field(None, description="续保起始日")
    renewal_end_date: Optional[date] = Field(None, description="续保到期日")
    cost: Optional[float] = Field(None, description="维保费用")
    remarks: Optional[str] = Field(None, description="备注")
    # — 新增字段 —
    warranty_no: Optional[str] = Field(None, max_length=50, description="维保单号")
    warranty_type: Optional[str] = Field(None, max_length=20, description="维保类型")
    warranty_vendor: Optional[str] = Field(None, max_length=100, description="维保供应商")


class WarrantyCreate(WarrantyBase):
    @field_validator('warranty_type')
    @classmethod
    def validate_warranty_type(cls, v):
        if v is not None and not is_valid_enum("warranty_type", v):
            raise ValueError(f"维保类型必须是系统配置中已启用的选项之一: {get_enum_values('warranty_type')}")
        return v


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
    warranty_no: Optional[str] = None
    warranty_type: Optional[str] = None
    warranty_vendor: Optional[str] = None


class WarrantyResponse(WarrantyBase):
    id: int
    class Config:
        from_attributes = True


# ============ 退役报废 ============
class RetirementBase(BaseModel):
    asset_code: str = Field(..., max_length=30, description="关联资产编号")
    retire_reason: Optional[str] = Field(None, description="报废原因")
    retire_category: Optional[str] = Field(None, max_length=20, description="报废类别")
    application_no: Optional[str] = Field(None, max_length=50, description="报废申请单号")
    approver: Optional[str] = Field(None, max_length=30, description="审批人")
    approval_date: Optional[date] = Field(None, description="审批日期")
    uninstall_date: Optional[date] = Field(None, description="下架日期")
    uninstall_person: Optional[str] = Field(None, max_length=30, description="下架人")
    data_cleared: Optional[str] = Field(None, max_length=20, description="数据清除确认")
    data_clear_person: Optional[str] = Field(None, max_length=30, description="数据清除人")
    disposal_method: Optional[str] = Field(None, max_length=30, description="处置方式")
    residual_value: Optional[float] = Field(None, description="残值回收")
    remarks: Optional[str] = Field(None, description="备注")


class RetirementCreate(RetirementBase):
    # BUG-004 修复：报废类别枚举校验
    @field_validator('retire_category')
    @classmethod
    def validate_retire_category(cls, v):
        if v is not None and not is_valid_enum("retire_category", v):
            raise ValueError(f"报废类别必须是系统配置中已启用的选项之一: {get_enum_values('retire_category')}")
        return v

    @field_validator('disposal_method')
    @classmethod
    def validate_disposal_method(cls, v):
        if v is not None and not is_valid_enum("disposal_method", v):
            raise ValueError(f"处置方式必须是系统配置中已启用的选项之一: {get_enum_values('disposal_method')}")
        return v


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
    severity: str  # "严重" | "中等"
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
    # — 新增7个枚举字段 —
    receive_types: list[str]
    outbound_categories: list[str]
    procurement_approval_statuses: list[str]
    warranty_types: list[str]
    disposal_methods: list[str]
    ownership_types: list[str]
    inbound_inspection_results: list[str]


# ============ 阶段门禁 ============
class StageGateResult(BaseModel):
    allowed: bool
    message: str


# ============ 审批工作流 ============
class ApprovalRequestCreate(BaseModel):
    approval_type: str = Field(..., description="审批类型枚举")
    asset_code: str = Field(..., max_length=30, description="目标资产编号")
    reason: str = Field(..., min_length=5, description="变更原因(至少5字)")
    attachments: list[str] = Field(default=[], description="附件路径列表")
    approver_ids: Optional[list[int]] = Field(None, description="指定审批人ID列表(按审批级别顺序)，不指定则自动指派")


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., description="审批动作: approve/reject")
    comment: Optional[str] = Field(None, description="审批意见(驳回时必填)")


class ApprovalSubmitRequest(BaseModel):
    approver_ids: Optional[list[int]] = Field(None, description="指定审批人ID列表(按审批级别顺序)，不指定则自动指派")


class ApprovalRequestResubmit(BaseModel):
    reason: Optional[str] = None
    attachments: Optional[list[str]] = None


class ApprovalStepResponse(BaseModel):
    id: int
    level: int
    approver_id: Optional[int] = None
    approver_role: str
    approver_name: Optional[str] = None
    status: str
    comment: Optional[str] = None
    acted_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class ApprovalRequestResponse(BaseModel):
    id: int
    request_no: str
    approval_type: str
    approval_type_name: Optional[str] = None
    asset_code: str
    current_stage: str
    target_stage: str
    reason: str
    attachments: list[str] = []
    status: str
    applicant_id: int
    applicant_name: Optional[str] = None
    applied_at: Optional[datetime] = None
    current_level: int = 1
    rejection_count: int = 0
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    steps: list[ApprovalStepResponse] = []
    class Config:
        from_attributes = True


class ApprovalNotificationResponse(BaseModel):
    id: int
    request_id: int
    request_no: Optional[str] = None
    user_id: int
    type: str
    title: str
    content: Optional[str] = None
    is_read: bool = False
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class ApprovalStatsResponse(BaseModel):
    total_pending: int
    my_pending: int
    my_applications: int
    unread_notifications: int
    by_type: dict[str, int]


class ApprovalTypeConfigItem(BaseModel):
    type_code: str
    type_name: str
    current_stage: str
    target_stage: str
    mode: str
    chain: list[dict]


class ApprovalDropdownConfig(BaseModel):
    approval_types: list[dict]  # [{code, name}]
    approval_statuses: list[dict]  # [{code, name}]
