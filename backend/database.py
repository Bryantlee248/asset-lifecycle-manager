"""数据库连接与模型定义 — 新台账模板v1.0"""
import os
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, Text, DateTime, Boolean, ForeignKey, Table, func, event, JSON, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship, Session
from datetime import datetime

_DB_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(_DB_DIR, '..', 'asset_lifecycle.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite 启用外键约束
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ 用户-角色关联表（多对多） ============
user_roles = Table(
    'user_roles', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)


# ============ 审计日志模型 ============
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, comment="操作用户ID")
    action = Column(String(20), comment="操作类型: create/update/delete")
    resource_type = Column(String(30), comment="资源类型")
    resource_id = Column(String(50), comment="资源ID/编号")
    detail = Column(Text, comment="操作详情")
    created_at = Column(DateTime, server_default=func.now())


# ============ 角色模型 ============
class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, comment="角色名称")
    code = Column(String(50), unique=True, nullable=False, comment="角色编码")
    description = Column(String(200), comment="角色描述")
    permissions = Column(Text, default="[]", comment="权限列表(JSON)")
    is_system = Column(Boolean, default=False, comment="是否系统内置角色")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    users = relationship("User", secondary=user_roles, back_populates="roles")


# ============ 用户模型 ============
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    real_name = Column(String(50), comment="真实姓名")
    email = Column(String(100), comment="邮箱")
    phone = Column(String(20), comment="手机号")
    department = Column(String(50), comment="部门")
    status = Column(String(20), default="active", comment="状态: active/disabled")
    last_login = Column(DateTime, comment="最后登录时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    roles = relationship("Role", secondary=user_roles, back_populates="users")


# ============ 资产台账主索引（新台账模板v1.0 — 34列） ============
class Asset(Base):
    __tablename__ = "assets"

    # — 保留字段 —
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), unique=True, nullable=False, comment="资产编号")
    asset_category = Column(String(20), nullable=False, comment="资产分类（第一类）")
    brand = Column(String(50), comment="品牌")
    model = Column(String(100), comment="型号")
    sn = Column(String(50), unique=True, comment="SN序列号")
    lifecycle_stage = Column(String(20), nullable=False, default="规划", comment="生命周期阶段")
    entry_date = Column(Date, comment="入场日期")
    responsible_person = Column(String(30), comment="责任人")
    warranty_status = Column(String(20), comment="维保状态")
    warranty_expire_date = Column(Date, comment="维保到期日")
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    remarks = Column(Text, comment="备注")

    # — 方案A：资产原值（单位元），迁移脚本 migrate_original_value.py 回填 —
    original_value = Column(Float, default=0.0, comment="资产原值(元)，方案A新增，迁移脚本回填")

    # — 新增字段（23个，严格按模板） —
    asset_category_2 = Column(String(50), comment="资产分类（第二类）")
    room = Column(String(50), comment="所在机房（如5-4机房）")
    cabinet = Column(String(20), comment="所在机柜（如R-03）")
    u_position = Column(String(20), comment="所在U位（如15-16U）")
    device_name = Column(String(100), comment="设备名称")
    project_name = Column(String(100), comment="项目名称")
    project_no = Column(String(50), comment="项目序号")
    size = Column(String(20), comment="尺寸（如2U/1U）")
    power_consumption = Column(Integer, comment="设备功耗（单位W）")
    ownership = Column(String(20), comment="产权归属（自有/托管）")
    department = Column(String(50), comment="所属部门")
    contract_no = Column(String(50), comment="合同编号")
    config_summary = Column(Text, comment="配置参数摘要")
    integrator_warranty_years = Column(Integer, comment="集成商维保年限（单位年）")
    integrator_warranty_start = Column(Date, comment="集成商维保起始时间")
    integrator_warranty_end = Column(Date, comment="集成商维保到期时间")
    integrator_warranty = Column(String(10), comment="集成商维保（是/否）")
    vendor_warranty_years = Column(Integer, comment="原厂维保年限（单位年）")
    vendor_warranty_start = Column(Date, comment="原厂维保起始时间")
    vendor_warranty_end = Column(Date, comment="原厂维保到期时间")
    vendor_warranty = Column(String(10), comment="原厂维保（是/否）")
    vendor_contact = Column(String(50), comment="厂家售后联系人")
    vendor_phone = Column(String(30), comment="电话")


# ============ 采购入库表（重构） ============
class Procurement(Base):
    __tablename__ = "procurement"

    # — 保留字段（asset_code改为nullable，移除ForeignKey约束） —
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), nullable=True, comment="关联资产编号（可选，采购不必须关联已有资产）")
    quantity = Column(Integer, default=1, comment="数量")
    unit_price = Column(Float, comment="单价")
    total_price = Column(Float, comment="总价")
    remarks = Column(Text, comment="备注")

    # — 新增字段 —
    request_no = Column(String(50), unique=True, comment="采购申请编号")
    vendor = Column(String(100), comment="供应商/原厂")
    device_name = Column(String(100), comment="设备名称")
    config_summary = Column(Text, comment="配置参数摘要")
    request_date = Column(Date, comment="申请日期")
    applicant = Column(String(30), comment="申请人")
    approval_status = Column(String(20), default="审批中", comment="审批状态")


# ============ 资产移入表（新增） ============
class AssetInbound(Base):
    __tablename__ = "asset_inbound"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), comment="关联资产编号（验收合格后回填，可空）")
    inbound_no = Column(String(50), comment="移入单号")
    receive_type = Column(String(20), comment="接收类型")
    ownership = Column(String(20), comment="产权归属")
    owner_company = Column(String(100), comment="产权方公司")
    project_name = Column(String(100), comment="项目名称")
    project_no = Column(String(50), comment="项目序号")
    asset_category = Column(String(20), comment="资产分类")
    brand = Column(String(50), comment="品牌")
    model = Column(String(100), comment="型号")
    sn = Column(String(50), comment="SN序列号")
    config_summary = Column(Text, comment="配置参数摘要")
    purchase_contract_no = Column(String(50), comment="采购合同编号")
    purchase_total_price = Column(Float, comment="采购总价")
    inbound_date = Column(Date, comment="移入日期")
    receiver = Column(String(30), comment="接收人")
    inspection_result = Column(String(20), comment="验收结果")
    storage_location = Column(String(100), comment="存放位置")
    remarks = Column(Text, comment="备注")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ============ 资产移出表（新增） ============
class AssetOutbound(Base):
    __tablename__ = "asset_outbound"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号（移出必须关联已有资产）")
    outbound_no = Column(String(50), comment="移出单号")
    outbound_reason = Column(Text, comment="移出原因")
    outbound_category = Column(String(20), comment="移出类别")
    destination = Column(String(100), comment="去向/目的地")
    outbound_date = Column(Date, comment="移出日期")
    receiver_contact = Column(String(50), comment="接收方联系人")
    receiver_phone = Column(String(30), comment="接收方联系电话")
    operator = Column(String(30), comment="操作人")
    approver = Column(String(30), comment="审批人")
    remarks = Column(Text, comment="备注")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ============ 变更迁移表（字段替换） ============
class Change(Base):
    __tablename__ = "changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    change_type = Column(String(20), nullable=False, comment="变更类型")
    # — 新增字段 —
    work_order_no = Column(String(50), comment="工单编号")
    change_content = Column(Text, comment="变更内容")
    old_config = Column(Text, comment="原配置")
    new_config = Column(Text, comment="新配置")
    # — 保留字段 —
    change_reason = Column(Text, comment="变更原因")
    approver = Column(String(30), comment="审批人")
    executor = Column(String(30), comment="执行人")
    execute_date = Column(Date, comment="执行日期")
    completion_status = Column(String(20), default="进行中", comment="完成状态")
    remarks = Column(Text, comment="备注")


# ============ 故障维修表（字段扩展） ============
class Fault(Base):
    __tablename__ = "faults"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    fault_level = Column(String(10), nullable=False, comment="故障等级P1/P2-严重/P3/P4")
    fault_description = Column(Text, comment="故障现象")
    fault_date = Column(Date, comment="故障日期")
    repair_person = Column(String(30), comment="维修人")
    handle_method = Column(String(30), comment="处理方式")
    parts_replaced = Column(Text, comment="配件更换记录")
    root_cause = Column(String(20), comment="根因分类")
    recovery_date = Column(Date, comment="恢复日期")
    downtime_hours = Column(Float, comment="停机时长(小时)")
    is_recurring = Column(Boolean, default=False, comment="是否复发")
    remarks = Column(Text, comment="备注")
    # — 新增字段 —
    fault_no = Column(String(50), unique=True, comment="故障单号")
    repair_cost = Column(Float, comment="维修费用")


# ============ 维保续保表（字段扩展） ============
class Warranty(Base):
    __tablename__ = "warranties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    contract_no = Column(String(50), comment="维保合同编号")
    coverage = Column(Text, comment="覆盖范围")
    start_date = Column(Date, comment="维保起始日")
    end_date = Column(Date, comment="维保到期日")
    renewal_decision = Column(String(20), comment="续保决策")
    decision_person = Column(String(30), comment="决策人")
    decision_date = Column(Date, comment="决策日期")
    renewal_contract_no = Column(String(50), comment="续保合同编号")
    renewal_start_date = Column(Date, comment="续保起始日")
    renewal_end_date = Column(Date, comment="续保到期日")
    cost = Column(Float, comment="维保费用")
    remarks = Column(Text, comment="备注")
    # — 新增字段 —
    warranty_no = Column(String(50), unique=True, comment="维保单号")
    warranty_type = Column(String(20), comment="维保类型")
    warranty_vendor = Column(String(100), comment="维保供应商")


# ============ 退役报废表 ============
class Retirement(Base):
    __tablename__ = "retirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    retire_reason = Column(Text, comment="报废原因")
    retire_category = Column(String(20), comment="报废类别")
    application_no = Column(String(50), comment="报废申请单号")
    approver = Column(String(30), comment="审批人")
    approval_date = Column(Date, comment="审批日期")
    uninstall_date = Column(Date, comment="下架日期")
    uninstall_person = Column(String(30), comment="下架人")
    data_cleared = Column(String(20), comment="数据清除确认")
    data_clear_person = Column(String(30), comment="数据清除人")
    disposal_method = Column(String(30), comment="处置方式")
    residual_value = Column(Float, comment="残值回收")
    remarks = Column(Text, comment="备注")


# ============ 审批工作流模型 ============
class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_no = Column(String(20), unique=True, nullable=False, comment="审批单号 APR-YYYYMMDD-SEQ")
    approval_type = Column(String(30), nullable=False, comment="审批类型枚举")
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="目标资产编号")
    current_stage = Column(String(20), nullable=False, comment="当前阶段")
    target_stage = Column(String(20), nullable=False, comment="目标阶段")
    reason = Column(Text, nullable=False, comment="变更原因")
    attachments = Column(Text, default="[]", comment="附件路径列表(JSON数组)")
    status = Column(String(20), nullable=False, default="draft", comment="状态: draft/pending/approved/rejected/cancelled")
    applicant_id = Column(Integer, ForeignKey('users.id'), nullable=False, comment="申请人ID")
    applied_at = Column(DateTime, comment="提交时间")
    current_level = Column(Integer, default=1, comment="当前审批级别")
    rejection_count = Column(Integer, default=0, comment="驳回次数")
    approved_at = Column(DateTime, comment="审批通过时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    steps = relationship("ApprovalStep", back_populates="request", cascade="all, delete-orphan")
    notifications = relationship("ApprovalNotification", back_populates="request", cascade="all, delete-orphan")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey('approval_requests.id', ondelete='CASCADE'), nullable=False, comment="关联审批单ID")
    level = Column(Integer, nullable=False, comment="审批级别 1=一级 2=二级")
    approver_id = Column(Integer, ForeignKey('users.id'), comment="审批人ID")
    approver_role = Column(String(30), nullable=False, comment="审批角色: ops_manager/admin")
    status = Column(String(20), nullable=False, default="pending", comment="步骤状态: pending/approved/rejected")
    comment = Column(Text, comment="审批意见(驳回时必填)")
    acted_at = Column(DateTime, comment="审批操作时间")

    request = relationship("ApprovalRequest", back_populates="steps")
    approver = relationship("User")


class ApprovalNotification(Base):
    __tablename__ = "approval_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey('approval_requests.id', ondelete='CASCADE'), nullable=False, comment="关联审批单ID")
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, comment="通知接收人ID")
    type = Column(String(30), nullable=False, comment="通知类型: pending_approval/approved/rejected/cancelled")
    title = Column(String(100), nullable=False, comment="通知标题")
    content = Column(Text, comment="通知内容")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, server_default=func.now())

    request = relationship("ApprovalRequest", back_populates="notifications")
    user = relationship("User")


# ============ 审批工作流模板（引擎单一数据源） ============
class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    approval_type = Column(String(30), unique=True, nullable=False, comment="审批类型枚举(与ApprovalRequest.approval_type对应)")
    approval_type_name = Column(String(50), nullable=False, comment="审批类型中文名(冗余存储，利于列表直出与审计)")
    current_stage = Column(String(20), nullable=False, comment="当前阶段或'*'(仅故障降级可用)")
    target_stage = Column(String(20), nullable=False, comment="目标阶段")
    mode = Column(String(10), nullable=False, default="single", comment="single/multi")
    chain = Column(JSON, nullable=False, comment="审批链节点数组[{level, role}]")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用(停用则禁止发起该类审批)")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def get_nodes(self) -> list:
        """返回审批链节点列表（兼容 class-diagram 设计）"""
        return self.chain if isinstance(self.chain, list) else []

    def node_count(self) -> int:
        """返回审批链节点数量"""
        return len(self.get_nodes())


# ============ 系统配置模块 P0：字典分组 / 字典项 / 资产分类 ============
class DictionaryGroup(Base):
    """字典分组（承载业务域 domain + 分组 group 两级，O7）"""
    __tablename__ = "dictionary_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain_code = Column(String(30), nullable=False, comment="业务域编码 如 fault_repair")
    domain_name = Column(String(50), nullable=False, comment="业务域名称 如 故障维修")
    group_code = Column(String(40), unique=True, nullable=False, comment="分组编码(唯一, dictionaries外键) 如 fault_level")
    group_name = Column(String(50), nullable=False, comment="分组名称 如 故障级别")
    sort_order = Column(Integer, default=0, comment="分组排序")
    is_system = Column(Boolean, default=True, comment="是否系统内置(种子写入)")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Dictionary(Base):
    """字典枚举项（同分组内 value 唯一，enabled 控制是否出现在下拉）"""
    __tablename__ = "dictionaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_code = Column(String(40), ForeignKey("dictionary_groups.group_code"), nullable=False, comment="所属分组")
    value = Column(String(50), nullable=False, comment="枚举值(用于校验与下拉显示) 如 P1")
    code = Column(String(30), nullable=True, comment="可选编码(枚举一般空; 预留)")
    sort_order = Column(Integer, default=0, comment="排序")
    enabled = Column(Boolean, default=True, comment="是否启用(停用不进新增下拉)")
    is_system = Column(Boolean, default=True, comment="是否系统内置")
    remark = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("ix_dictionaries_group_enabled", "group_code", "enabled"),
        UniqueConstraint("group_code", "value", name="uq_dict_group_value"),  # A-01: 同分组内 value 唯一
    )


class Category(Base):
    """资产分类（O1 / O6：独立表，驱动资产编号 category_code；仅 category_name 唯一）"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(50), unique=True, nullable=False, comment="分类中文名(唯一) 如 服务器/PDU")
    category_code = Column(String(10), nullable=False, comment="分类码 如 SVR/PDU; O6放宽:不唯一(配电设备与PDU同映射PDU)")
    sort_order = Column(Integer, default=0, comment="排序")
    enabled = Column(Boolean, default=True, comment="是否启用")
    is_system = Column(Boolean, default=True, comment="是否系统内置")
    remark = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("ix_categories_name", "category_name"),
        Index("ix_categories_code_enabled", "category_code", "enabled"),
        # O6: 仅 category_name 唯一; category_code 不 unique（容纳 PDU 碰撞）
    )


# ============ 阶段变更事件日志（报表统计模块 P2：S-16/S-17 数据底座） ============
class AssetStageLog(Base):
    """资产生命周期阶段变更事件日志。

    前向钩子（真实变更）写入 is_backfill=False；历史回填推演值写入 is_backfill=True。
    趋势（stage-trend）与对比（compare）接口均基于本表月末快照推演。
    """
    __tablename__ = "asset_stage_log"
    __table_args__ = (
        Index("ix_asset_stage_log_code", "asset_code"),
        Index("ix_asset_stage_log_changed_at", "changed_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), nullable=False, comment="关联资产编号(assets.asset_code)")
    from_stage = Column(String(20), comment="变更前阶段")
    to_stage = Column(String(20), nullable=False, comment="变更后阶段")
    changed_at = Column(DateTime, nullable=False, comment="变更发生时刻(前向取真实时刻/回填取推演日期 00:00:00)")
    operator = Column(String(30), comment="操作人(前向取真实操作人/回填=system_backfill)")
    reason = Column(String(200), comment="变更原因")
    is_backfill = Column(Boolean, default=False, comment="是否历史推演回填值")


def record_stage_change(
    db: Session,
    asset_code: str,
    from_stage: str,
    to_stage: str,
    changed_at,
    operator: str,
    reason: str,
    is_backfill: bool = False,
) -> None:
    """统一写入阶段变更日志（前向/回填均经此入口）。

    - 仅 db.add，不 commit（由调用方事务统一提交）。
    - from_stage == to_stage 时跳过，避免「维修→维修」空转。
    - changed_at 为 datetime；回填场景传 datetime.combine(date, time.min)。
    """
    if from_stage == to_stage:
        return
    log = AssetStageLog(
        asset_code=asset_code,
        from_stage=from_stage or "",
        to_stage=to_stage,
        changed_at=changed_at,
        operator=operator or "system",
        reason=(reason or "")[:200],
        is_backfill=is_backfill,
    )
    db.add(log)


# 创建所有表
Base.metadata.create_all(bind=engine)
