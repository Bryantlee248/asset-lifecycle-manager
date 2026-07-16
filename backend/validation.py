"""校验服务 — 新台账模板v1.0的10项自动检查（替换原13项）
严重度体系：严重/中等（替代原error/warning）
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date, timedelta
from database import (
    Asset, Procurement, Change, Fault, Warranty, Retirement,
    AssetInbound, AssetOutbound
)
from schemas import ValidationItem, ValidationDashboard


def run_all_checks(db: Session) -> ValidationDashboard:
    """执行10项校验检查"""
    checks = []
    total_severe = 0
    total_moderate = 0

    # 1. 编号为空（严重）
    empty_codes = db.query(Asset).filter(
        or_(Asset.asset_code == None, Asset.asset_code == '')
    ).count()
    empty_code_records = db.query(Asset).filter(
        or_(Asset.asset_code == None, Asset.asset_code == '')
    ).all()[:10]
    checks.append(ValidationItem(
        check_name="编号为空", description="资产编号为空的记录",
        count=empty_codes, severity="严重",
        details=[a.asset_code or "(空)" for a in empty_code_records]
    ))
    total_severe += empty_codes

    # 2. SN号为空（严重） — 非报废阶段
    empty_sn = db.query(Asset).filter(
        or_(Asset.sn == None, Asset.sn == ''),
        Asset.lifecycle_stage != "已报废"
    ).count()
    empty_sn_records = db.query(Asset).filter(
        or_(Asset.sn == None, Asset.sn == ''),
        Asset.lifecycle_stage != "已报废"
    ).all()[:10]
    checks.append(ValidationItem(
        check_name="SN号为空", description="非报废阶段SN序列号为空",
        count=empty_sn, severity="严重",
        details=[f"{a.asset_code}: SN为空(阶段:{a.lifecycle_stage})" for a in empty_sn_records]
    ))
    total_severe += empty_sn

    # 3. 位置为空（严重） — 非报废阶段，room/cabinet/u_position任一为空
    empty_position = db.query(Asset).filter(
        Asset.lifecycle_stage != "已报废",
        or_(
            Asset.room == None, Asset.room == '',
            Asset.cabinet == None, Asset.cabinet == '',
            Asset.u_position == None, Asset.u_position == '',
        )
    ).count()
    empty_position_records = db.query(Asset).filter(
        Asset.lifecycle_stage != "已报废",
        or_(
            Asset.room == None, Asset.room == '',
            Asset.cabinet == None, Asset.cabinet == '',
            Asset.u_position == None, Asset.u_position == '',
        )
    ).all()[:10]
    pos_details = []
    for a in empty_position_records:
        missing = []
        if not a.room:
            missing.append("机房")
        if not a.cabinet:
            missing.append("机柜")
        if not a.u_position:
            missing.append("U位")
        pos_details.append(f"{a.asset_code}: 缺少{','.join(missing)}")
    checks.append(ValidationItem(
        check_name="位置为空", description="非报废阶段设备机房/机柜/U位任一为空",
        count=empty_position, severity="严重",
        details=pos_details
    ))
    total_severe += empty_position

    # 4. 责任人为空（中等） — 上架/运行/维修阶段
    empty_resp = db.query(Asset).filter(
        or_(Asset.responsible_person == None, Asset.responsible_person == ''),
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).count()
    empty_resp_records = db.query(Asset).filter(
        or_(Asset.responsible_person == None, Asset.responsible_person == ''),
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).all()[:10]
    checks.append(ValidationItem(
        check_name="责任人为空", description="上架/运行/维修阶段设备无责任人",
        count=empty_resp, severity="中等",
        details=[f"{a.asset_code}: 无责任人(阶段:{a.lifecycle_stage})" for a in empty_resp_records]
    ))
    total_moderate += empty_resp

    # 5. 阶段为空（严重）
    empty_stage = db.query(Asset).filter(
        or_(Asset.lifecycle_stage == None, Asset.lifecycle_stage == '')
    ).count()
    checks.append(ValidationItem(
        check_name="阶段为空", description="生命周期阶段为空",
        count=empty_stage, severity="严重",
        details=[]
    ))
    total_severe += empty_stage

    # 6. 编号重复（严重）
    dup_codes = db.query(Asset.asset_code, func.count(Asset.asset_code)).filter(
        Asset.asset_code != None, Asset.asset_code != ''
    ).group_by(Asset.asset_code).having(func.count(Asset.asset_code) > 1).all()
    dup_count = sum(c[1] - 1 for c in dup_codes)
    checks.append(ValidationItem(
        check_name="编号重复", description="资产编号出现>1次",
        count=dup_count, severity="严重",
        details=[f"{c[0]}: 出现{c[1]}次" for c in dup_codes[:10]]
    ))
    total_severe += dup_count

    # 7. 维保已过期(运行状态)（中等）
    today = date.today()
    expired_warranty = db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage == "运行"
    ).count()
    expired_records = db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage == "运行"
    ).all()[:10]
    checks.append(ValidationItem(
        check_name="维保已过期(运行状态)", description="运行阶段维保已过期",
        count=expired_warranty, severity="中等",
        details=[f"{a.asset_code}: 维保已于{a.warranty_expire_date}过期" for a in expired_records]
    ))
    total_moderate += expired_warranty

    # 8. 维保到期日早于入场日期（严重）
    bad_dates = db.query(Asset).filter(
        Asset.warranty_expire_date != None,
        Asset.entry_date != None,
        Asset.warranty_expire_date < Asset.entry_date
    ).count()
    bad_date_records = db.query(Asset).filter(
        Asset.warranty_expire_date != None,
        Asset.entry_date != None,
        Asset.warranty_expire_date < Asset.entry_date
    ).all()[:10]
    checks.append(ValidationItem(
        check_name="维保到期日早于入场日期", description="warranty_expire_date < entry_date",
        count=bad_dates, severity="严重",
        details=[f"{a.asset_code}: 到期{a.warranty_expire_date}早于入场{a.entry_date}" for a in bad_date_records]
    ))
    total_severe += bad_dates

    # 9. 已报废但报废表无记录（严重）
    retired_codes = set(r.asset_code for r in db.query(Retirement.asset_code).all())
    scrapped_assets = db.query(Asset.asset_code).filter(Asset.lifecycle_stage == "已报废").all()
    no_retirement_details = [f"{a.asset_code}: 已报废但退役表无记录" for a in scrapped_assets if a.asset_code not in retired_codes]
    no_retirement = len(no_retirement_details)
    checks.append(ValidationItem(
        check_name="已报废但报废表无记录", description="阶段='已报废'且Retirement表无对应记录",
        count=no_retirement, severity="严重",
        details=no_retirement_details[:10]
    ))
    total_severe += no_retirement

    # 10. 分表编号不在主表中（中等） — 含asset_inbound和asset_outbound
    asset_codes = set(a.asset_code for a in db.query(Asset.asset_code).filter(
        Asset.asset_code != None, Asset.asset_code != ''
    ).all())
    orphan_count = 0
    orphan_details = []
    for table_cls, table_name in [
        (Procurement, "采购入库"),
        (Change, "变更迁移"),
        (Fault, "故障维修"),
        (Warranty, "维保续保"),
        (Retirement, "退役报废"),
        (AssetInbound, "资产移入"),
        (AssetOutbound, "资产移出"),
    ]:
        # 只检查有asset_code字段的记录
        orphan_records = db.query(table_cls.asset_code).filter(
            table_cls.asset_code != None,
            table_cls.asset_code != '',
            ~table_cls.asset_code.in_(asset_codes)
        ).all()
        for r in orphan_records:
            orphan_count += 1
            orphan_details.append(f"{table_name}表: 编号{r.asset_code}在主表不存在")
    checks.append(ValidationItem(
        check_name="分表编号不在主表中", description="所有子表的asset_code不在assets表中",
        count=orphan_count, severity="中等",
        details=orphan_details[:10]
    ))
    total_moderate += orphan_count

    total_assets = db.query(Asset).count()

    return ValidationDashboard(
        total_assets=total_assets,
        total_errors=total_severe,
        total_warnings=total_moderate,
        checks=checks
    )


def check_stage_gate(db: Session, asset_code: str, target_stage: str) -> dict:
    """检查阶段跳转是否满足前置条件（阶段门禁）"""
    asset = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if not asset:
        return {"allowed": False, "message": f"资产编号 {asset_code} 不存在"}

    current = asset.lifecycle_stage

    # 定义合法的阶段跳转路径
    valid_transitions = {
        "规划": ["在途", "上架"],
        "在途": ["上架", "运行"],
        "上架": ["运行"],
        "运行": ["维修", "待报废", "在途"],
        "维修": ["运行", "待报废"],
        "待报废": ["已报废"],
    }

    if target_stage not in valid_transitions.get(current, []):
        return {"allowed": False, "message": f"不允许从 '{current}' 跳转到 '{target_stage}'。合法跳转: {valid_transitions.get(current, [])}"}

    # 检查特定跳转的前置条件
    if target_stage == "已报废":
        retirement = db.query(Retirement).filter(Retirement.asset_code == asset_code).first()
        if not retirement or not retirement.application_no:
            return {"allowed": False, "message": "报废需要先在退役报废表填写报废申请单号"}
        if not retirement.data_cleared or retirement.data_cleared != "已清除":
            return {"allowed": False, "message": "报废需要先确认数据已清除"}

    if target_stage == "上架" and current == "在途":
        procurement = db.query(Procurement).filter(Procurement.asset_code == asset_code).first()
        if procurement and procurement.inspection_result and procurement.inspection_result != "合格":
            return {"allowed": False, "message": "上架需要验收结果为'合格'"}
        # 也检查移入表的验收结果
        inbound = db.query(AssetInbound).filter(AssetInbound.asset_code == asset_code).first()
        if inbound and inbound.inspection_result and inbound.inspection_result != "合格":
            return {"allowed": False, "message": "上架需要验收结果为'合格'"}
        # 如果两者都有记录但都不是合格
        if procurement and inbound:
            if procurement.inspection_result != "合格" and inbound.inspection_result != "合格":
                return {"allowed": False, "message": "上架需要验收结果为'合格'"}

    if target_stage == "运行" and current == "上架":
        # 上架→运行需要位置信息完整
        if not asset.room or not asset.cabinet or not asset.u_position:
            missing = []
            if not asset.room:
                missing.append("机房")
            if not asset.cabinet:
                missing.append("机柜")
            if not asset.u_position:
                missing.append("U位")
            return {"allowed": False, "message": f"上架→运行需要完整位置信息，缺少: {','.join(missing)}"}

    if target_stage == "运行" and current == "维修":
        # BUG-001 修复：三铁规则——无记录不执行
        fault_count = db.query(Fault).filter(Fault.asset_code == asset_code).count()
        if fault_count == 0:
            return {"allowed": False, "message": "维修阶段恢复运行需要至少一条故障记录（无记录不执行）"}
        unrecovered = db.query(Fault).filter(Fault.asset_code == asset_code, Fault.recovery_date == None).first()
        if unrecovered:
            return {"allowed": False, "message": "恢复运行需要先填写所有故障的恢复日期"}

    return {"allowed": True, "message": f"可以从 '{current}' 跳转到 '{target_stage}'"}
