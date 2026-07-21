"""系统配置模块 P0 配置管理 API — 字典/枚举 + 资产分类 CRUD + 引用保护 + 缓存失效

路由前缀：/api/config
风格对齐 reports_stats.py：模块内纯函数 + APIRouter；main.py 仅 include_router。
所有写接口经 require_permission("config:manage") 保护；写成功后 invalidate_and_rebuild 重建枚举缓存。
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, field_validator

from database import get_db, DictionaryGroup, Dictionary, Category, StageTransitionRule, Asset, ValidationRuleSwitch, AggregateWhitelist
from auth import require_permission, User
from config_cache import invalidate_and_rebuild, count_references
from constants import LIFECYCLE_STAGES

config_router = APIRouter(prefix="/api/config", tags=["系统配置"])


# ============ 请求体 Schema ============
class DictionaryGroupCreate(BaseModel):
    domain_code: str = Field(..., max_length=30, description="业务域编码")
    domain_name: str = Field(..., max_length=50, description="业务域名称")
    group_code: str = Field(..., max_length=40, description="分组编码(唯一)")
    group_name: str = Field(..., max_length=50, description="分组名称")
    sort_order: int = 0


class DictionaryGroupUpdate(BaseModel):
    domain_name: Optional[str] = Field(None, max_length=50)
    group_name: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[int] = None


class DictionaryCreate(BaseModel):
    group_code: str = Field(..., max_length=40, description="所属分组编码")
    value: str = Field(..., max_length=50, description="枚举值")
    code: Optional[str] = Field(None, max_length=30, description="可选编码")
    sort_order: int = 0
    remark: Optional[str] = None
    enabled: bool = True


class DictionaryUpdate(BaseModel):
    value: Optional[str] = Field(None, max_length=50)
    code: Optional[str] = Field(None, max_length=30)
    sort_order: Optional[int] = None
    remark: Optional[str] = None
    enabled: Optional[bool] = None


class CategoryCreate(BaseModel):
    category_name: str = Field(..., max_length=50, description="分类中文名(唯一)")
    category_code: str = Field(..., max_length=10, pattern=r"^[A-Z0-9]{2,4}$", description="分类码(大写字母/数字 2-4 位)")
    remark: Optional[str] = None
    sort_order: int = 0
    enabled: bool = True


class CategoryUpdate(BaseModel):
    category_name: Optional[str] = Field(None, max_length=50)
    category_code: Optional[str] = Field(None, max_length=10, pattern=r"^[A-Z0-9]{2,4}$")
    remark: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


# ============ 通用：写后缓存失效 ============
def _after_write(db: Session) -> None:
    invalidate_and_rebuild(db)


# ============ 字典分组管理 ============
@config_router.get("/dictionary-groups")
def list_dictionary_groups(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """分组列表（按 domain 聚合在前端完成），含 is_system 标记。"""
    return db.query(DictionaryGroup).order_by(DictionaryGroup.sort_order, DictionaryGroup.id).all()


@config_router.post("/dictionary-groups")
def create_dictionary_group(body: DictionaryGroupCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    existing = db.query(DictionaryGroup).filter(DictionaryGroup.group_code == body.group_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"分组编码 {body.group_code} 已存在")
    group = DictionaryGroup(
        domain_code=body.domain_code, domain_name=body.domain_name,
        group_code=body.group_code, group_name=body.group_name,
        sort_order=body.sort_order, is_system=False,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    _after_write(db)
    return group


@config_router.put("/dictionary-groups/{group_id}")
def update_dictionary_group(group_id: int, body: DictionaryGroupUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    group = db.query(DictionaryGroup).filter(DictionaryGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if body.domain_name is not None:
        group.domain_name = body.domain_name
    if body.group_name is not None:
        group.group_name = body.group_name
    if body.sort_order is not None:
        group.sort_order = body.sort_order
    db.commit()
    db.refresh(group)
    _after_write(db)
    return group


@config_router.delete("/dictionary-groups/{group_id}")
def delete_dictionary_group(group_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    group = db.query(DictionaryGroup).filter(DictionaryGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if group.is_system:
        raise HTTPException(status_code=400, detail="系统内置分组不可删除")
    child_count = db.query(Dictionary).filter(Dictionary.group_code == group.group_code).count()
    if child_count > 0:
        raise HTTPException(status_code=400, detail=f"该分组下还有 {child_count} 个枚举项，请先清空")
    db.delete(group)
    db.commit()
    _after_write(db)
    return {"ok": True}


# ============ 枚举项管理 ============
@config_router.get("/dictionaries")
def list_dictionaries(group_code: str = Query(..., description="分组编码"), db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """枚举项列表（含 disabled，供管理页显隐/启用）。"""
    return db.query(Dictionary).filter(Dictionary.group_code == group_code).order_by(Dictionary.sort_order, Dictionary.id).all()


@config_router.post("/dictionaries")
def create_dictionary(body: DictionaryCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    group = db.query(DictionaryGroup).filter(DictionaryGroup.group_code == body.group_code).first()
    if not group:
        raise HTTPException(status_code=400, detail=f"分组 {body.group_code} 不存在")
    d = Dictionary(
        group_code=body.group_code, value=body.value, code=body.code,
        sort_order=body.sort_order, enabled=body.enabled, is_system=False, remark=body.remark,
    )
    db.add(d)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"分组 {body.group_code} 下枚举值 '{body.value}' 已存在")
    db.refresh(d)
    _after_write(db)
    return d


@config_router.put("/dictionaries/{dict_id}")
def update_dictionary(dict_id: int, body: DictionaryUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    d = db.query(Dictionary).filter(Dictionary.id == dict_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="枚举项不存在")
    if body.value is not None:
        d.value = body.value
    if body.code is not None:
        d.code = body.code
    if body.sort_order is not None:
        d.sort_order = body.sort_order
    if body.remark is not None:
        d.remark = body.remark
    if body.enabled is not None:
        d.enabled = body.enabled
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"分组 {d.group_code} 下枚举值 '{body.value}' 已存在")
    db.refresh(d)
    _after_write(db)
    return d


@config_router.delete("/dictionaries/{dict_id}")
def delete_dictionary(dict_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """A-05 引用保护：被引用项禁止物理删除（O2）。"""
    d = db.query(Dictionary).filter(Dictionary.id == dict_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="枚举项不存在")
    count = count_references(db, d.group_code, d.value)
    if count > 0:
        raise HTTPException(status_code=400, detail=f"该选项被 {count} 条记录引用，禁止删除，仅可停用")
    db.delete(d)
    db.commit()
    _after_write(db)
    return {"ok": True}


@config_router.post("/dictionaries/{dict_id}/toggle")
def toggle_dictionary(dict_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    d = db.query(Dictionary).filter(Dictionary.id == dict_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="枚举项不存在")
    d.enabled = not d.enabled
    db.commit()
    db.refresh(d)
    _after_write(db)
    return d


@config_router.post("/dictionaries/reorder")
def reorder_dictionaries(body: ReorderRequest, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    for item in body.items:
        d = db.query(Dictionary).filter(Dictionary.id == item.id).first()
        if d:
            d.sort_order = item.sort_order
    db.commit()
    _after_write(db)
    return {"ok": True}


# ============ 资产分类管理 ============
@config_router.get("/categories")
def list_categories(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """分类列表（含 disabled）。"""
    return db.query(Category).order_by(Category.sort_order, Category.id).all()


@config_router.post("/categories")
def create_category(body: CategoryCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    c = Category(
        category_name=body.category_name, category_code=body.category_code,
        sort_order=body.sort_order, enabled=body.enabled, is_system=False, remark=body.remark,
    )
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"分类名 '{body.category_name}' 已存在")
    db.refresh(c)
    _after_write(db)
    return c


@config_router.put("/categories/{cat_id}")
def update_category(cat_id: int, body: CategoryUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    c = db.query(Category).filter(Category.id == cat_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="分类不存在")
    if body.category_name is not None:
        c.category_name = body.category_name
    if body.category_code is not None:
        c.category_code = body.category_code
    if body.remark is not None:
        c.remark = body.remark
    if body.sort_order is not None:
        c.sort_order = body.sort_order
    if body.enabled is not None:
        c.enabled = body.enabled
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"分类名 '{body.category_name}' 已存在")
    db.refresh(c)
    _after_write(db)
    return c


@config_router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """B-04 引用保护：被 assets/asset_inbound 引用的分类禁止物理删除（O2）。"""
    c = db.query(Category).filter(Category.id == cat_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="分类不存在")
    count = count_references(db, "category", c.category_name)
    if count > 0:
        raise HTTPException(status_code=400, detail=f"该分类被 {count} 条记录引用，禁止删除，仅可停用")
    db.delete(c)
    db.commit()
    _after_write(db)
    return {"ok": True}


@config_router.post("/categories/{cat_id}/toggle")
def toggle_category(cat_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    c = db.query(Category).filter(Category.id == cat_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="分类不存在")
    c.enabled = not c.enabled
    db.commit()
    db.refresh(c)
    _after_write(db)
    return c


# ============ 引用计数（删除前预警） ============
@config_router.get("/references")
def get_references(kind: str = Query(..., description="引用类型(group_code 或 'category')"), value: str = Query(..., description="枚举值/分类名"), db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    count = count_references(db, kind, value)
    return {"count": count, "referenced": count > 0}


# ============ 阶段流转矩阵管理（系统配置模块 P1，design §3.3） ============
class StageTransitionRuleCreate(BaseModel):
    from_stage: str = Field(..., description="源阶段")
    to_stage: str = Field(..., description="目标阶段")
    allowed: bool = True
    require_approval: bool = True
    require_fault_record: bool = False
    require_data_cleared: bool = False
    require_retirement: bool = False
    require_inspection: bool = False
    require_location: bool = False
    remark: Optional[str] = None
    sort_order: int = 0

    @field_validator("from_stage", "to_stage")
    @classmethod
    def _valid_stage(cls, v):
        # 非法阶段值（非 7 阶段之一）→ schema 校验失败 → 422（design §7 / T-11）
        if v not in LIFECYCLE_STAGES:
            raise ValueError(f"非法阶段值: {v}（须为 {LIFECYCLE_STAGES} 之一）")
        return v


class StageTransitionRuleUpdate(BaseModel):
    allowed: Optional[bool] = None
    require_approval: Optional[bool] = None
    require_fault_record: Optional[bool] = None
    require_data_cleared: Optional[bool] = None
    require_retirement: Optional[bool] = None
    require_inspection: Optional[bool] = None
    require_location: Optional[bool] = None
    remark: Optional[str] = None
    sort_order: Optional[int] = None


class StageTransitionImport(BaseModel):
    rules: List[StageTransitionRuleCreate]


@config_router.get("/stage-transitions")
def list_stage_transitions(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """阶段流转规则列表（含禁用），按 from_stage/sort_order 排序。"""
    return db.query(StageTransitionRule).order_by(
        StageTransitionRule.from_stage, StageTransitionRule.sort_order, StageTransitionRule.id
    ).all()


@config_router.post("/stage-transitions")
def create_stage_transition(body: StageTransitionRuleCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """新增阶段流转规则（is_system=False）；重复 (from,to) → 400。"""
    existing = db.query(StageTransitionRule).filter(
        StageTransitionRule.from_stage == body.from_stage,
        StageTransitionRule.to_stage == body.to_stage,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"阶段对 ({body.from_stage}→{body.to_stage}) 已存在")
    rule = StageTransitionRule(
        from_stage=body.from_stage, to_stage=body.to_stage,
        allowed=body.allowed, require_approval=body.require_approval,
        require_fault_record=body.require_fault_record,
        require_data_cleared=body.require_data_cleared,
        require_retirement=body.require_retirement,
        require_inspection=body.require_inspection,
        require_location=body.require_location,
        remark=body.remark, is_system=False, sort_order=body.sort_order,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"阶段对 ({body.from_stage}→{body.to_stage}) 已存在（唯一约束冲突）")
    db.refresh(rule)
    _after_write(db)
    return rule


@config_router.put("/stage-transitions/{rule_id}")
def update_stage_transition(rule_id: int, body: StageTransitionRuleUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """更新阶段流转规则的标志/允许/备注；写后失效缓存。"""
    rule = db.query(StageTransitionRule).filter(StageTransitionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="流转规则不存在")
    for f in ["allowed", "require_approval", "require_fault_record", "require_data_cleared",
               "require_retirement", "require_inspection", "require_location", "remark", "sort_order"]:
        val = getattr(body, f)
        if val is not None:
            setattr(rule, f, val)
    db.commit()
    db.refresh(rule)
    _after_write(db)
    return rule


@config_router.delete("/stage-transitions/{rule_id}")
def delete_stage_transition(rule_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """删除阶段流转规则（出口保护，O2 / design §3.5）。"""
    rule = db.query(StageTransitionRule).filter(StageTransitionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="流转规则不存在")
    if rule.is_system:
        raise HTTPException(status_code=400, detail="系统内置规则不可删除")
    # 出口保护：本规则是 allowed 出口、且该阶段其它 allowed 出口为 0、且存在存量资产 → 禁止
    if rule.allowed:
        other = db.query(StageTransitionRule).filter(
            StageTransitionRule.from_stage == rule.from_stage,
            StageTransitionRule.allowed == True,
            StageTransitionRule.id != rule.id,
        ).count()
        if other == 0:
            asset_cnt = db.query(Asset).filter(Asset.lifecycle_stage == rule.from_stage).count()
            if asset_cnt > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"该阶段仅有此一条允许出口且存在 {asset_cnt} 条存量资产，禁止删除（可改为停用）",
                )
    db.delete(rule)
    db.commit()
    _after_write(db)
    return {"ok": True}


@config_router.post("/stage-transitions/{rule_id}/toggle")
def toggle_stage_transition(rule_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """启停(允许/禁止)某条流转规则；写后失效缓存。"""
    rule = db.query(StageTransitionRule).filter(StageTransitionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="流转规则不存在")
    rule.allowed = not rule.allowed
    db.commit()
    db.refresh(rule)
    _after_write(db)
    return rule


@config_router.get("/stage-transitions/export")
def export_stage_transitions(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """导出全部阶段流转规则为 JSON 数组。"""
    rules = db.query(StageTransitionRule).order_by(
        StageTransitionRule.from_stage, StageTransitionRule.sort_order, StageTransitionRule.id
    ).all()
    return [r.to_dict() for r in rules]


@config_router.post("/stage-transitions/import")
def import_stage_transitions(body: StageTransitionImport, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """批量导入阶段流转规则（JSON + upsert，design §3.6）。"""
    created = updated = 0
    for item in body.rules:
        existing = db.query(StageTransitionRule).filter(
            StageTransitionRule.from_stage == item.from_stage,
            StageTransitionRule.to_stage == item.to_stage,
        ).first()
        if existing:
            for f in ["allowed", "require_approval", "require_fault_record", "require_data_cleared",
                       "require_retirement", "require_inspection", "require_location", "remark", "sort_order"]:
                setattr(existing, f, getattr(item, f))
            updated += 1
        else:
            db.add(StageTransitionRule(
                from_stage=item.from_stage, to_stage=item.to_stage,
                allowed=item.allowed, require_approval=item.require_approval,
                require_fault_record=item.require_fault_record,
                require_data_cleared=item.require_data_cleared,
                require_retirement=item.require_retirement,
                require_inspection=item.require_inspection,
                require_location=item.require_location,
                remark=item.remark, is_system=False, sort_order=item.sort_order,
            ))
            created += 1
    db.commit()
    _after_write(db)
    return {"created": created, "updated": updated}


# ============ 系统配置模块 P2：校验规则开关管理（design §3.3 / §3.4） ============
# 校验规则开关粒度 = 单条规则（10 项与 rule_key 一一对应，O1）；仅可启停/备注，不可新增/删除系统项。
ASSET_COLUMNS = set(Asset.__table__.columns.keys())  # Asset 合法列名集合


class ValidationRuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    remark: Optional[str] = None


class ValidationRuleImportItem(BaseModel):
    rule_key: str
    enabled: bool = True
    remark: Optional[str] = None


class ValidationRuleImport(BaseModel):
    rules: List[ValidationRuleImportItem]


@config_router.get("/validation-rules")
def list_validation_rules(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """校验开关列表（含禁用），按 sort_order/id 排序。"""
    return db.query(ValidationRuleSwitch).order_by(
        ValidationRuleSwitch.sort_order, ValidationRuleSwitch.id
    ).all()


@config_router.put("/validation-rules/{rule_id}")
def update_validation_rule(rule_id: int, body: ValidationRuleUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """更新校验开关（仅 enabled / remark；rule_key/check_name/severity 只读）。"""
    rule = db.query(ValidationRuleSwitch).filter(ValidationRuleSwitch.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="校验规则不存在")
    if body.enabled is not None:
        rule.enabled = body.enabled
    if body.remark is not None:
        rule.remark = body.remark
    db.commit()
    db.refresh(rule)
    _after_write(db)
    return rule


@config_router.post("/validation-rules/{rule_id}/toggle")
def toggle_validation_rule(rule_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """启停某条校验规则；写后失效缓存。"""
    rule = db.query(ValidationRuleSwitch).filter(ValidationRuleSwitch.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="校验规则不存在")
    rule.enabled = not rule.enabled
    db.commit()
    db.refresh(rule)
    _after_write(db)
    return rule


@config_router.get("/validation-rules/export")
def export_validation_rules(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """导出全部校验开关为 JSON 数组。"""
    rules = db.query(ValidationRuleSwitch).order_by(
        ValidationRuleSwitch.sort_order, ValidationRuleSwitch.id
    ).all()
    return [r.to_dict() for r in rules]


@config_router.post("/validation-rules/import")
def import_validation_rules(body: ValidationRuleImport, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """批量导入校验开关（JSON + upsert，design §3.4）。"""
    created = updated = 0
    for item in body.rules:
        existing = db.query(ValidationRuleSwitch).filter(ValidationRuleSwitch.rule_key == item.rule_key).first()
        if existing:
            existing.enabled = item.enabled
            if item.remark is not None:
                existing.remark = item.remark
            updated += 1
        else:
            # 配置快照容错：rule_key 不存在时作为自定义行插入（run_all_checks 仅识别固定 10 个 rule_key）
            db.add(ValidationRuleSwitch(
                rule_key=item.rule_key, check_name=item.rule_key, description=None,
                severity="中等", enabled=item.enabled, remark=item.remark,
                is_system=False, sort_order=(db.query(ValidationRuleSwitch).count() or 0) + 1,
            ))
            created += 1
    db.commit()
    _after_write(db)
    return {"created": created, "updated": updated}


@config_router.post("/validation-rules/reset")
def reset_validation_rules(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """恢复默认（seed 出厂态）：seed 行 enabled 重置为 true；删除管理员自定义(is_system=false)行。"""
    for row in db.query(ValidationRuleSwitch).all():
        if row.is_system:
            row.enabled = True  # 还原为全开出厂态（remark 保留管理员备注）
        else:
            db.delete(row)      # 自定义行非出厂项，重置即清掉
    db.commit()
    _after_write(db)
    return {"ok": True}


# ============ 系统配置模块 P2：聚合维度白名单管理（design §3.3 / §3.4） ============
# 聚合白名单粒度 = 维度级（11 字段各自独立启停，O2）；允许新增非原 11 字段的 Asset 合法列名（O3）。
class AggregateFieldCreate(BaseModel):
    field_key: str = Field(..., description="Asset 列名(唯一,须为合法列)")
    field_label: str = Field(..., description="展示名")
    metric_support: str = "count,original_value"
    remark: Optional[str] = None
    sort_order: int = 0

    @field_validator("field_key")
    @classmethod
    def _valid_column(cls, v):
        # 非法列名 → schema 校验失败 → 422（design §8）
        if v not in ASSET_COLUMNS:
            raise ValueError(f"非法聚合字段: {v}（非 Asset 合法列名）")
        return v


class AggregateFieldUpdate(BaseModel):
    field_label: Optional[str] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None


class AggregateFieldImportItem(BaseModel):
    field_key: str
    field_label: str
    enabled: bool = True
    metric_support: str = "count,original_value"
    remark: Optional[str] = None


class AggregateFieldImport(BaseModel):
    fields: List[AggregateFieldImportItem]


@config_router.get("/aggregate-fields")
def list_aggregate_fields(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """聚合维度列表（含禁用），按 sort_order/id 排序。"""
    return db.query(AggregateWhitelist).order_by(
        AggregateWhitelist.sort_order, AggregateWhitelist.id
    ).all()


@config_router.get("/aggregate-field-columns")
def list_aggregate_field_columns(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """返回 Asset 全部合法列名（新增聚合维度时的候选字段下拉源，design §9.2 主理人拍板采用后端枚举端点）。

    仅列合法列名（排除主键 id），前端据此下拉选择，避免硬编码常量；最终仍以 field_validator 校验（422）。
    """
    return [c.name for c in Asset.__table__.columns if c.name != "id"]


@config_router.post("/aggregate-fields")
def create_aggregate_field(body: AggregateFieldCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """新增聚合维度（field_key 须合法列名且唯一）；非法列→422；重复→400；is_system=False。"""
    existing = db.query(AggregateWhitelist).filter(AggregateWhitelist.field_key == body.field_key).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"聚合维度 {body.field_key} 已存在")
    field = AggregateWhitelist(
        field_key=body.field_key, field_label=body.field_label,
        metric_support=body.metric_support, enabled=True,
        remark=body.remark, is_system=False, sort_order=body.sort_order,
    )
    db.add(field)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"聚合维度 {body.field_key} 已存在（唯一约束冲突）")
    db.refresh(field)
    _after_write(db)
    return field


@config_router.put("/aggregate-fields/{field_id}")
def update_aggregate_field(field_id: int, body: AggregateFieldUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """更新聚合维度（enabled/remark/field_label）；写后失效。"""
    field = db.query(AggregateWhitelist).filter(AggregateWhitelist.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="聚合维度不存在")
    if body.field_label is not None:
        field.field_label = body.field_label
    if body.enabled is not None:
        field.enabled = body.enabled
    if body.remark is not None:
        field.remark = body.remark
    db.commit()
    db.refresh(field)
    _after_write(db)
    return field


@config_router.delete("/aggregate-fields/{field_id}")
def delete_aggregate_field(field_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """删除聚合维度；is_system 行禁删（400），否则删。"""
    field = db.query(AggregateWhitelist).filter(AggregateWhitelist.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="聚合维度不存在")
    if field.is_system:
        raise HTTPException(status_code=400, detail="系统内置维度不可删除（仅可停用）")
    db.delete(field)
    db.commit()
    _after_write(db)
    return {"ok": True}


@config_router.post("/aggregate-fields/{field_id}/toggle")
def toggle_aggregate_field(field_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """启停某条聚合维度；写后失效缓存。"""
    field = db.query(AggregateWhitelist).filter(AggregateWhitelist.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="聚合维度不存在")
    field.enabled = not field.enabled
    db.commit()
    db.refresh(field)
    _after_write(db)
    return field


@config_router.get("/aggregate-fields/export")
def export_aggregate_fields(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """导出全部聚合维度为 JSON 数组。"""
    fields = db.query(AggregateWhitelist).order_by(
        AggregateWhitelist.sort_order, AggregateWhitelist.id
    ).all()
    return [f.to_dict() for f in fields]


@config_router.post("/aggregate-fields/import")
def import_aggregate_fields(body: AggregateFieldImport, db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """批量导入聚合维度（JSON + upsert，design §3.4）。"""
    created = updated = 0
    for item in body.fields:
        if item.field_key not in ASSET_COLUMNS:
            raise HTTPException(status_code=422, detail=f"非法聚合字段: {item.field_key}（非 Asset 合法列名）")
        existing = db.query(AggregateWhitelist).filter(AggregateWhitelist.field_key == item.field_key).first()
        if existing:
            existing.field_label = item.field_label
            existing.enabled = item.enabled
            existing.metric_support = item.metric_support
            if item.remark is not None:
                existing.remark = item.remark
            updated += 1
        else:
            db.add(AggregateWhitelist(
                field_key=item.field_key, field_label=item.field_label,
                metric_support=item.metric_support, enabled=item.enabled,
                remark=item.remark, is_system=False,
                sort_order=(db.query(AggregateWhitelist).count() or 0) + 1,
            ))
            created += 1
    db.commit()
    _after_write(db)
    return {"created": created, "updated": updated}


@config_router.post("/aggregate-fields/reset")
def reset_aggregate_fields(db: Session = Depends(get_db), _: User = Depends(require_permission("config:manage"))):
    """恢复默认（seed 出厂态）：seed 行 enabled 重置为 true；删除管理员自定义(is_system=false)行。"""
    for row in db.query(AggregateWhitelist).all():
        if row.is_system:
            row.enabled = True
        else:
            db.delete(row)
    db.commit()
    _after_write(db)
    return {"ok": True}
