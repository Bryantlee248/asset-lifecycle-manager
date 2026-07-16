"""系统配置模块 P0 配置管理 API — 字典/枚举 + 资产分类 CRUD + 引用保护 + 缓存失效

路由前缀：/api/config
风格对齐 reports_stats.py：模块内纯函数 + APIRouter；main.py 仅 include_router。
所有写接口经 require_permission("config:manage") 保护；写成功后 invalidate_and_rebuild 重建枚举缓存。
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field

from database import get_db, DictionaryGroup, Dictionary, Category
from auth import require_permission, User
from config_cache import invalidate_and_rebuild, count_references

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
