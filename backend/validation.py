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
from config_cache import (
    get_gate_rule, get_allowed_targets, build_stage_gate_cache,
    get_enabled_validation_rule_keys, build_validation_rules_cache,
)
from schemas import ValidationItem, ValidationDashboard


def run_all_checks(db: Session) -> ValidationDashboard:
    """执行10项校验检查。

    单一集成入口：读 validation_rule_switch 表（经进程内缓存），仅执行 enabled 的规则。
    返回结构 ValidationDashboard(total_assets, total_errors, total_warnings, checks) 不变，
    4 类调用方（GET /api/validation 及任何触发校验处）零改动自动切换。
    默认（全 enabled）时 10 块全部执行，与原硬编码逐条一致；关闭某项 → 该项不 append、不计入总量。
    """
    # 读进程内校验开关缓存；未建则回退查表并重建（design §4.1）
    enabled_keys = get_enabled_validation_rule_keys()
    if enabled_keys is None:
        build_validation_rules_cache(db)
        enabled_keys = get_enabled_validation_rule_keys() or set()

    checks = []
    total_severe = 0
    total_moderate = 0

    # 1. 编号为空（严重）
    if "empty_code" in enabled_keys:
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
    if "empty_sn" in enabled_keys:
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
    if "empty_position" in enabled_keys:
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
    if "empty_responsible" in enabled_keys:
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
    if "empty_stage" in enabled_keys:
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
    if "duplicate_code" in enabled_keys:
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
    if "warranty_expired" in enabled_keys:
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
    if "warranty_date_invalid" in enabled_keys:
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
    if "retired_no_record" in enabled_keys:
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
    if "orphan_subtable_code" in enabled_keys:
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
    """检查阶段跳转是否满足前置条件（阶段门禁，design §3.4）。

    单一集成入口：读 stage_transition_rule 表（经进程内缓存），按 allow + require_*
    标志执行前置校验。返回契约 {"allowed":bool, "message":str} 不变，
    4 个调用方（main.update_asset / get_stage_gate / approval.submit_approval /
    approval.drive_stage_change）零改动。
    """
    asset = db.query(Asset).filter(Asset.asset_code == asset_code).first()
    if not asset:
        return {"allowed": False, "message": f"资产编号 {asset_code} 不存在"}
    current = asset.lifecycle_stage

    # 读进程内阶段流转缓存；未建则回退查表并重建（design §4.1）
    rule = get_gate_rule(current, target_stage)
    if rule is None:
        build_stage_gate_cache(db)
        rule = get_gate_rule(current, target_stage)

    if rule is None or not rule["allowed"]:
        legal = get_allowed_targets(current) or ["（无允许出口）"]
        return {
            "allowed": False,
            "message": f"不允许从 '{current}' 跳转到 '{target_stage}'。合法跳转: {legal}",
        }

    # 按 require_* 标志执行前置校验（与原硬编码 4 分支逐条等价）
    if rule["require_retirement"]:
        retirement = db.query(Retirement).filter(Retirement.asset_code == asset_code).first()
        if not retirement or not retirement.application_no:
            return {"allowed": False, "message": "需要先在退役报废表填写报废申请单号"}
    if rule["require_data_cleared"]:
        retirement = db.query(Retirement).filter(Retirement.asset_code == asset_code).first()
        if not retirement or not retirement.data_cleared or retirement.data_cleared != "已清除":
            return {"allowed": False, "message": "需要先确认数据已清除"}
    if rule["require_inspection"]:
        procurement = db.query(Procurement).filter(Procurement.asset_code == asset_code).first()
        if procurement and procurement.inspection_result and procurement.inspection_result != "合格":
            return {"allowed": False, "message": "上架需要验收结果为'合格'"}
        inbound = db.query(AssetInbound).filter(AssetInbound.asset_code == asset_code).first()
        if inbound and inbound.inspection_result and inbound.inspection_result != "合格":
            return {"allowed": False, "message": "上架需要验收结果为'合格'"}
    if rule["require_location"]:
        if not asset.room or not asset.cabinet or not asset.u_position:
            missing = [m for m, v in (
                ("机房", asset.room), ("机柜", asset.cabinet), ("U位", asset.u_position)
            ) if not v]
            return {"allowed": False, "message": f"需要完整位置信息，缺少: {','.join(missing)}"}
    if rule["require_fault_record"]:
        if db.query(Fault).filter(Fault.asset_code == asset_code).count() == 0:
            return {"allowed": False, "message": "维修阶段恢复运行需要至少一条故障记录"}
        if db.query(Fault).filter(Fault.asset_code == asset_code, Fault.recovery_date == None).first():
            return {"allowed": False, "message": "恢复运行需要先填写所有故障的恢复日期"}
    return {"allowed": True, "message": f"可以从 '{current}' 跳转到 '{target_stage}'"}
