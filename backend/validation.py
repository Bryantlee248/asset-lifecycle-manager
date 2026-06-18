"""校验服务 - 替代Excel校验仪表盘的13项自动检查"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from database import Asset, Procurement, Change, Fault, Warranty, Retirement
from schemas import ValidationItem, ValidationDashboard


def run_all_checks(db: Session) -> ValidationDashboard:
    checks = []
    total_errors = 0
    total_warnings = 0

    # 1. 资产编号空值检查
    empty_codes = db.query(Asset).filter(Asset.asset_code == None).count()
    checks.append(ValidationItem(
        check_name="编号空值", description="资产编号为空的记录",
        count=empty_codes, severity="error",
        details=[a.asset_code or "(空)" for a in db.query(Asset).filter(Asset.asset_code == None).all()[:10]]
    ))
    total_errors += empty_codes

    # 2. SN号空值检查
    empty_sn = db.query(Asset).filter(Asset.sn == None).count()
    checks.append(ValidationItem(
        check_name="SN空值", description="SN序列号为空的记录",
        count=empty_sn, severity="warning",
        details=[f"{a.asset_code}: SN为空" for a in db.query(Asset).filter(Asset.sn == None).all()[:10]]
    ))
    total_warnings += empty_sn

    # 3. 位置空值检查
    empty_loc = db.query(Asset).filter(Asset.location == None, Asset.lifecycle_stage != "已报废").count()
    checks.append(ValidationItem(
        check_name="位置空值", description="非报废设备位置为空",
        count=empty_loc, severity="warning",
        details=[f"{a.asset_code}: 位置为空" for a in db.query(Asset).filter(Asset.location == None, Asset.lifecycle_stage != "已报废").all()[:10]]
    ))
    total_warnings += empty_loc

    # 4. 责任人空值检查
    empty_resp = db.query(Asset).filter(Asset.responsible_person == None, Asset.lifecycle_stage.in_(["上架", "运行", "维修"])).count()
    checks.append(ValidationItem(
        check_name="责任人空值", description="运行阶段设备无责任人",
        count=empty_resp, severity="error",
        details=[f"{a.asset_code}: 无责任人" for a in db.query(Asset).filter(Asset.responsible_person == None, Asset.lifecycle_stage.in_(["上架", "运行", "维修"])).all()[:10]]
    ))
    total_errors += empty_resp

    # 5. 阶段空值检查
    empty_stage = db.query(Asset).filter(Asset.lifecycle_stage == None).count()
    checks.append(ValidationItem(
        check_name="阶段空值", description="生命周期阶段为空",
        count=empty_stage, severity="error",
        details=[]
    ))
    total_errors += empty_stage

    # 6. 编号重复检查
    dup_codes = db.query(Asset.asset_code, func.count(Asset.asset_code)).group_by(Asset.asset_code).having(func.count(Asset.asset_code) > 1).all()
    dup_count = sum(c[1] - 1 for c in dup_codes)
    checks.append(ValidationItem(
        check_name="编号重复", description="资产编号重复",
        count=dup_count, severity="error",
        details=[f"{c[0]}: 出现{c[1]}次" for c in dup_codes[:10]]
    ))
    total_errors += dup_count

    # 7. 位置重复检查（非报废设备）
    dup_locs = db.query(Asset.location, func.count(Asset.location)).filter(
        Asset.lifecycle_stage != "已报废", Asset.location != None
    ).group_by(Asset.location).having(func.count(Asset.location) > 1).all()
    dup_loc_count = sum(c[1] - 1 for c in dup_locs)
    checks.append(ValidationItem(
        check_name="位置重复", description="非报废设备同一位置有多台设备",
        count=dup_loc_count, severity="warning",
        details=[f"位置{c[0]}: {c[1]}台设备" for c in dup_locs[:10]]
    ))
    total_warnings += dup_loc_count

    # 8. 维保过期未续保
    today = date.today()
    expired_warranty = db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"]),
        Asset.warranty_status != "续保中"
    ).count()
    expired_details = [f"{a.asset_code}: 维保已于{a.warranty_expire_date}过期" for a in db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"]),
        Asset.warranty_status != "续保中"
    ).all()[:10]]
    checks.append(ValidationItem(
        check_name="维保过期", description="维保已过期且未续保的运行设备（裸跑风险）",
        count=expired_warranty, severity="error",
        details=expired_details
    ))
    total_errors += expired_warranty

    # 9. 维保30天内到期
    soon_expire = db.query(Asset).filter(
        Asset.warranty_expire_date.between(today, today + timedelta(days=30)),
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).count()
    checks.append(ValidationItem(
        check_name="维保即将到期", description="维保30天内到期",
        count=soon_expire, severity="warning",
        details=[f"{a.asset_code}: 维保将于{a.warranty_expire_date}到期" for a in db.query(Asset).filter(
            Asset.warranty_expire_date.between(today, today + timedelta(days=30)),
            Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
        ).all()[:10]]
    ))
    total_warnings += soon_expire

    # 10. 日期逻辑矛盾（入场日期>报废相关日期）
    # This is complex, simplified check: entry_date > today
    bad_dates = db.query(Asset).filter(Asset.entry_date > today).count()
    checks.append(ValidationItem(
        check_name="日期矛盾", description="入场日期在未来",
        count=bad_dates, severity="error",
        details=[]
    ))
    total_errors += bad_dates

    # 11. 已报废但无退役记录
    retired_codes = set(r.asset_code for r in db.query(Retirement.asset_code).all())
    scrapped_assets = db.query(Asset.asset_code).filter(Asset.lifecycle_stage == "已报废").all()
    no_retirement_details = [f"{a.asset_code}: 已报废但无退役记录" for a in scrapped_assets if a.asset_code not in retired_codes]
    no_retirement = len(no_retirement_details)
    checks.append(ValidationItem(
        check_name="报废无记录", description="已报废但退役报废表无对应记录",
        count=no_retirement, severity="error",
        details=no_retirement_details[:10]
    ))
    total_errors += no_retirement

    # 12. 孤儿记录（分表有记录但主表无对应编号）
    asset_codes = set(a.asset_code for a in db.query(Asset.asset_code).all())
    orphan_count = 0
    orphan_details = []
    for table_cls, table_name in [(Procurement, "采购入库"), (Change, "变更迁移"), (Fault, "故障维修"), (Warranty, "维保续保"), (Retirement, "退役报废")]:
        orphan_records = db.query(table_cls.asset_code).filter(
            ~table_cls.asset_code.in_(asset_codes)
        ).all()
        for r in orphan_records:
            orphan_count += 1
            orphan_details.append(f"{table_name}表: 编号{r.asset_code}在主表不存在")
    checks.append(ValidationItem(
        check_name="孤儿记录", description="分表记录关联的编号在主表中不存在",
        count=orphan_count, severity="error",
        details=orphan_details[:10]
    ))
    total_errors += orphan_count

    # 13. P1/P2故障未恢复
    critical_unresolved = db.query(Fault).filter(
        Fault.fault_level.in_(["P1", "P2"]),
        Fault.recovery_date == None
    ).count()
    checks.append(ValidationItem(
        check_name="P1/P2未恢复", description="P1/P2级别故障尚未恢复",
        count=critical_unresolved, severity="error",
        details=[f"{f.asset_code}: {f.fault_level}故障未恢复" for f in db.query(Fault).filter(
            Fault.fault_level.in_(["P1", "P2"]), Fault.recovery_date == None
        ).all()[:10]]
    ))
    total_errors += critical_unresolved

    total_assets = db.query(Asset).count()

    return ValidationDashboard(
        total_assets=total_assets,
        total_errors=total_errors,
        total_warnings=total_warnings,
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
        "在途": ["上架"],
        "上架": ["运行"],
        "运行": ["维修", "待报废"],
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
        if procurement and procurement.inspection_result != "合格":
            return {"allowed": False, "message": "上架需要验收结果为'合格'"}

    if target_stage == "运行" and current == "维修":
        fault = db.query(Fault).filter(Fault.asset_code == asset_code, Fault.recovery_date == None).first()
        if fault:
            return {"allowed": False, "message": "恢复运行需要先填写故障恢复日期"}

    return {"allowed": True, "message": f"可以从 '{current}' 跳转到 '{target_stage}'"}