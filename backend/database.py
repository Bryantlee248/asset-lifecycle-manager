"""数据库连接与模型定义"""
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, Text, DateTime, Boolean, ForeignKey, Table, func, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./asset_lifecycle.db"

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


# ============ 资产台账主索引 ============
class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), unique=True, nullable=False, comment="资产编号")
    asset_category = Column(String(20), nullable=False, comment="资产分类")
    brand = Column(String(50), comment="品牌")
    model = Column(String(100), comment="型号")
    sn = Column(String(50), unique=True, comment="SN序列号")
    location = Column(String(30), comment="位置(机房-列-柜-位)")
    lifecycle_stage = Column(String(20), nullable=False, default="规划", comment="生命周期阶段")
    entry_date = Column(Date, comment="入场日期")
    responsible_person = Column(String(30), comment="责任人")
    warranty_status = Column(String(20), comment="维保状态")
    warranty_expire_date = Column(Date, comment="维保到期日")
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    ip_address = Column(String(50), comment="IP地址")
    remarks = Column(Text, comment="备注")


# ============ 采购入库表 ============
class Procurement(Base):
    __tablename__ = "procurement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    purchase_order = Column(String(50), comment="采购单号")
    contract_no = Column(String(50), comment="合同号")
    supplier = Column(String(100), comment="供应商")
    quantity = Column(Integer, default=1, comment="数量")
    unit_price = Column(Float, comment="单价")
    total_price = Column(Float, comment="总价")
    arrival_date = Column(Date, comment="到货日期")
    inspector = Column(String(30), comment="验收人")
    inspection_result = Column(String(20), comment="验收结果")
    install_date = Column(Date, comment="上架日期")
    remarks = Column(Text, comment="备注")


# ============ 变更迁移表 ============
class Change(Base):
    __tablename__ = "changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    change_type = Column(String(20), nullable=False, comment="变更类型")
    old_location = Column(String(30), comment="原位置")
    new_location = Column(String(30), comment="新位置")
    old_ip = Column(String(50), comment="原IP")
    new_ip = Column(String(50), comment="新IP")
    old_responsible = Column(String(30), comment="原责任人")
    new_responsible = Column(String(30), comment="新责任人")
    change_reason = Column(Text, comment="变更原因")
    approver = Column(String(30), comment="审批人")
    executor = Column(String(30), comment="执行人")
    execute_date = Column(Date, comment="执行日期")
    completion_status = Column(String(20), default="进行中", comment="完成状态")
    remarks = Column(Text, comment="备注")


# ============ 故障维修表 ============
class Fault(Base):
    __tablename__ = "faults"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), ForeignKey('assets.asset_code'), nullable=False, comment="关联资产编号")
    fault_level = Column(String(10), nullable=False, comment="故障等级P1-P4")
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


# ============ 维保续保表 ============
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


# 创建所有表
Base.metadata.create_all(bind=engine)
