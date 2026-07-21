"""Append 50 deterministic, scenario-based IT asset test records to the local database."""
from dataclasses import dataclass
from datetime import date, timedelta
import os
import sys


BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import (  # noqa: E402
    Asset,
    AssetInbound,
    AssetOutbound,
    Change,
    Fault,
    Procurement,
    Retirement,
    SessionLocal,
    Warranty,
)


SCENARIO_PREFIX = "DC-CL-SIM-"


@dataclass(frozen=True)
class Scenario:
    name: str
    stage: str
    count: int
    records: tuple[str, ...]


SCENARIOS = (
    Scenario("规划采购", "规划", 6, ("procurement",)),
    Scenario("在途交付", "在途", 6, ("procurement",)),
    Scenario("上架验收", "上架", 8, ("inbound",)),
    Scenario("正常运行", "运行", 10, ("inbound", "warranty")),
    Scenario("临期维保", "运行", 5, ("inbound", "warranty", "expiring")),
    Scenario("P1 故障维修", "维修", 5, ("inbound", "active_fault")),
    Scenario("P3 故障已恢复", "维修", 4, ("inbound", "resolved_fault")),
    Scenario("变更迁移", "运行", 3, ("inbound", "change")),
    Scenario("待报废审批", "待报废", 2, ("inbound", "retirement")),
    Scenario("已报废移出", "已报废", 1, ("inbound", "retirement", "outbound")),
)

CATEGORIES = ("服务器", "网络设备", "存储设备", "安全设备", "UPS")
BRANDS = ("Dell", "华为", "H3C", "NetApp", "APC")
RESPONSIBLE_PEOPLE = ("张伟", "李娜", "王强", "陈静", "赵敏")
VENDOR = "模拟数据中心设备供应商"


def asset_code(sequence: int) -> str:
    return f"{SCENARIO_PREFIX}{sequence:03d}"


def seed_scenario_test_data(db) -> dict[str, int]:
    """Append missing scenario records and return the counts created in this run."""
    today = date.today()
    summary = {
        "assets_created": 0,
        "procurement_created": 0,
        "inbound_created": 0,
        "warranty_created": 0,
        "fault_created": 0,
        "change_created": 0,
        "retirement_created": 0,
        "outbound_created": 0,
    }
    sequence = 201
    record_sequence = {"procurement": 1, "inbound": 1, "warranty": 1, "fault": 1, "change": 1, "retirement": 1, "outbound": 1}

    existing_codes = {
        row[0]
        for row in db.query(Asset.asset_code)
        .filter(Asset.asset_code.like(f"{SCENARIO_PREFIX}%"))
        .all()
    }

    for scenario in SCENARIOS:
        for _ in range(scenario.count):
            code = asset_code(sequence)
            current_sequence = sequence
            sequence += 1
            if code in existing_codes:
                continue

            category = CATEGORIES[(current_sequence - 201) % len(CATEGORIES)]
            brand = BRANDS[(current_sequence - 201) % len(BRANDS)]
            person = RESPONSIBLE_PEOPLE[(current_sequence - 201) % len(RESPONSIBLE_PEOPLE)]
            entry_date = None if scenario.stage in ("规划", "在途") else today - timedelta(days=180 + current_sequence)
            has_warranty = "warranty" in scenario.records
            expires_soon = "expiring" in scenario.records

            db.add(
                Asset(
                    asset_code=code,
                    asset_category=category,
                    brand=brand,
                    model=f"SIM-{category}-{current_sequence}",
                    sn=f"SIMSN{current_sequence:06d}",
                    lifecycle_stage=scenario.stage,
                    entry_date=entry_date,
                    responsible_person=None if scenario.stage in ("规划", "在途") else person,
                    warranty_status="即将过期" if expires_soon else "在保" if has_warranty else "待定",
                    warranty_expire_date=today + timedelta(days=20 if expires_soon else 365) if has_warranty else None,
                    room=None if scenario.stage == "规划" else "模拟 A 区机房",
                    cabinet=None if scenario.stage == "规划" else f"SIM-R-{(current_sequence % 12) + 1:02d}",
                    u_position=None if scenario.stage == "规划" else f"{(current_sequence % 40) + 1}U",
                    device_name=f"{scenario.name}-{category}-{current_sequence}",
                    project_name="SIM 场景化测试项目",
                    project_no="SIM-2026-01",
                    size="2U",
                    power_consumption=800,
                    ownership="自有",
                    department="信息技术部",
                    contract_no=f"SIM-CT-{current_sequence:03d}",
                    config_summary="双路电源，冗余网络，模拟场景化测试配置",
                    remarks=f"模拟场景：{scenario.name}",
                )
            )
            db.flush()
            summary["assets_created"] += 1

            if "procurement" in scenario.records:
                record_no = record_sequence["procurement"]
                db.add(
                    Procurement(
                        asset_code=code,
                        quantity=1,
                        unit_price=50000,
                        total_price=50000,
                        request_no=f"SIM-PR-{record_no:03d}",
                        vendor=VENDOR,
                        device_name=f"{category} 模拟采购设备",
                        config_summary="模拟采购配置",
                        request_date=today - timedelta(days=30),
                        applicant=person,
                        approval_status="审批中",
                    )
                )
                record_sequence["procurement"] += 1
                summary["procurement_created"] += 1

            if "inbound" in scenario.records:
                record_no = record_sequence["inbound"]
                db.add(
                    AssetInbound(
                        asset_code=code,
                        inbound_no=f"SIM-IB-{record_no:03d}",
                        receive_type="采购入库",
                        ownership="自有",
                        owner_company="模拟数据中心",
                        project_name="SIM 场景化测试项目",
                        project_no="SIM-2026-01",
                        asset_category=category,
                        brand=brand,
                        model=f"SIM-{category}-{current_sequence}",
                        sn=f"SIMSN{current_sequence:06d}",
                        config_summary="模拟入库配置",
                        purchase_contract_no=f"SIM-CT-{current_sequence:03d}",
                        purchase_total_price=50000,
                        inbound_date=entry_date or today,
                        receiver=person,
                        inspection_result="合格",
                        storage_location="模拟 A 区机房-SIM 货架",
                    )
                )
                record_sequence["inbound"] += 1
                summary["inbound_created"] += 1

            if "warranty" in scenario.records:
                record_no = record_sequence["warranty"]
                warranty_end = today + timedelta(days=20 if expires_soon else 365)
                db.add(
                    Warranty(
                        asset_code=code,
                        warranty_no=f"SIM-WT-{record_no:03d}",
                        warranty_type="原厂维保",
                        warranty_vendor=VENDOR,
                        contract_no=f"SIM-WC-{record_no:03d}",
                        coverage="整机硬件与现场技术支持",
                        start_date=entry_date or today,
                        end_date=warranty_end,
                        renewal_decision="待评估" if expires_soon else "续保",
                        decision_person=person,
                        decision_date=today,
                        cost=6000,
                    )
                )
                record_sequence["warranty"] += 1
                summary["warranty_created"] += 1

            if "active_fault" in scenario.records or "resolved_fault" in scenario.records:
                record_no = record_sequence["fault"]
                active_fault = "active_fault" in scenario.records
                db.add(
                    Fault(
                        asset_code=code,
                        fault_no=f"SIM-FT-{record_no:03d}",
                        fault_level="P1" if active_fault else "P3",
                        fault_description="模拟硬件故障，覆盖维修处置场景",
                        fault_date=today - timedelta(days=2),
                        repair_person=person,
                        handle_method="更换备件",
                        parts_replaced="模拟电源模块",
                        root_cause="硬件故障",
                        recovery_date=None if active_fault else today - timedelta(days=1),
                        downtime_hours=4.5 if active_fault else 1.0,
                        is_recurring=False,
                    )
                )
                record_sequence["fault"] += 1
                summary["fault_created"] += 1

            if "change" in scenario.records:
                record_no = record_sequence["change"]
                db.add(
                    Change(
                        asset_code=code,
                        change_type="迁移",
                        work_order_no=f"SIM-CH-{record_no:03d}",
                        change_content="模拟机柜迁移与网络链路调整",
                        old_config="原机柜：SIM-R-01",
                        new_config="新机柜：SIM-R-08",
                        change_reason="模拟容量扩容迁移",
                        approver="张伟",
                        executor=person,
                        execute_date=today - timedelta(days=7),
                        completion_status="已完成",
                    )
                )
                record_sequence["change"] += 1
                summary["change_created"] += 1

            if "retirement" in scenario.records:
                record_no = record_sequence["retirement"]
                db.add(
                    Retirement(
                        asset_code=code,
                        retire_reason="模拟设备达到更新周期",
                        retire_category="报废",
                        application_no=f"SIM-RT-{record_no:03d}",
                        approver="张伟",
                        approval_date=today - timedelta(days=10),
                        uninstall_date=today - timedelta(days=5),
                        uninstall_person=person,
                        data_cleared="已清除",
                        data_clear_person=person,
                        disposal_method="回收",
                        residual_value=1000,
                    )
                )
                record_sequence["retirement"] += 1
                summary["retirement_created"] += 1

            if "outbound" in scenario.records:
                record_no = record_sequence["outbound"]
                db.add(
                    AssetOutbound(
                        asset_code=code,
                        outbound_no=f"SIM-OB-{record_no:03d}",
                        outbound_reason="模拟报废移出",
                        outbound_category="报废",
                        destination="模拟回收处理中心",
                        outbound_date=today - timedelta(days=1),
                        receiver_contact="模拟回收联系人",
                        receiver_phone="13800002001",
                        operator=person,
                        approver="张伟",
                    )
                )
                record_sequence["outbound"] += 1
                summary["outbound_created"] += 1

    db.commit()
    return summary


def main() -> None:
    db = SessionLocal()
    try:
        summary = seed_scenario_test_data(db)
    finally:
        db.close()
    for name, count in summary.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
