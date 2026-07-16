"""IT资产全生命周期管理系统 v3.0.0 — 全套测试数据生成脚本

直写 SQLite 数据库（asset_lifecycle.db），覆盖全部 8 张核心业务表：
    assets / procurement / asset_inbound / asset_outbound
    changes / faults / warranties / retirements

设计要点：
    1. 通过导入 backend.database 复用其 engine（已配置相对路径指向正确 DB），
       并在会话上显式开启 PRAGMA foreign_keys=ON。
    2. 幂等：运行前先清空所有子表，再清空 assets，保证每次重跑都是干净 100 条。
    3. 插入顺序：先插 100 台 assets 并 flush，再插各子表以满足外键依赖，最后统一 commit。
    4. random.seed(42) 保证可复现。
    5. 生成的枚举字段值严格来自 constants.py；数据尽量通过 validation.py 的 10 项校验。
"""

import os
import sys
from datetime import date, timedelta

# ---- 将 backend 加入 sys.path，复用其 engine / SessionLocal / 模型 / 常量 ----
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from database import (  # noqa: E402
    engine,
    SessionLocal,
    Asset,
    Procurement,
    AssetInbound,
    AssetOutbound,
    Change,
    Fault,
    Warranty,
    Retirement,
)
from constants import (  # noqa: E402
    CATEGORIES,
    LIFECYCLE_STAGES,
    WARRANTY_STATUSES,
    RECEIVE_TYPES,
    OUTBOUND_CATEGORIES,
    PROCUREMENT_APPROVAL_STATUSES,
    WARRANTY_TYPES,
    DISPOSAL_METHODS,
    OWNERSHIP_TYPES,
    INBOUND_INSPECTION_RESULTS,
    FAULT_LEVELS,
    HANDLE_METHODS,
    ROOT_CAUSES,
    RENEWAL_DECISIONS,
    RETIRE_CATEGORIES,
    DATA_CLEAR_OPTIONS,
    COMPLETION_STATUSES,
    CHANGE_TYPES,
)

import random

random.seed(42)

TOTAL_ASSETS = 100
TODAY = date.today()


# ============================ 基础工具 ============================
def rand_date(start_year: int = 2022, end_year: int = 2025) -> date:
    """返回 [start_year-01-01, end_year-12-31] 之间的随机日期。"""
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    span = (end - start).days
    return start + timedelta(days=random.randint(0, span))


def future_date(start_offset_days: int = 30, end_offset_days: int = 365 * 3) -> date:
    """返回相对今天之后的随机日期，用于运行阶段维保到期（严格晚于今天，避免过期告警）。"""
    start = TODAY + timedelta(days=start_offset_days)
    end = TODAY + timedelta(days=end_offset_days)
    span = (end - start).days
    return start + timedelta(days=random.randint(0, span))


def clamp_past(d: date) -> date:
    """确保日期不晚于今天（用于故障/运维类历史记录更真实）。"""
    return d if d <= TODAY else TODAY - timedelta(days=random.randint(0, 30))


# ============================ 拟真数据池 ============================
# 分类 -> 资产编号前缀
CATEGORY_CODE = {
    "服务器": "SRV",
    "网络设备": "NET",
    "存储设备": "STG",
    "安全设备": "SEC",
    "UPS": "UPS",
    "配电设备": "PWR",
    "空调": "AC",
    "KVM": "KVM",
    "PDU": "PDU",
    "其他": "OTH",
}

# 分类 -> (品牌, 型号) 池
CATEGORY_BRANDS = {
    "服务器": [
        ("Dell", "R740xd"),
        ("HP", "DL380 Gen10"),
        ("联想", "SR650"),
        ("华为", "2288H V5"),
        ("浪潮", "NF5280M5"),
        ("超聚变", "R5300 G5"),
    ],
    "网络设备": [
        ("华为", "S5731-H24T4XC"),
        ("思科", "C9300-24T"),
        ("华三", "S6800"),
        ("锐捷", "RG-S5750"),
        ("迈普", "MyPower S4320"),
        ("Juniper", "EX4300"),
    ],
    "存储设备": [
        ("华为", "OceanStor 5310"),
        ("戴尔", "PowerStore 1000T"),
        ("NetApp", "FAS2750"),
        ("浪潮", "AS5500"),
        ("联想", "ThinkSystem DE4000"),
    ],
    "安全设备": [
        ("深信服", "AF-1000"),
        ("天融信", "TopIDP"),
        ("启明星辰", "NIPS-2000"),
        ("绿盟", "NIDS-3000"),
        ("奇安信", "SG-6000"),
    ],
    "UPS": [
        ("维谛", "Liebert GXE"),
        ("施耐德", "APC Smart-UPS 3000"),
        ("伊顿", "Eaton 9355"),
        ("科华", "YTR"),
        ("山特", "Castle 3C10KS"),
    ],
    "配电设备": [
        ("良信", "NDM3"),
        ("正泰", "NA8"),
        ("施耐德", "Prisma"),
        ("ABB", "Emax 2"),
    ],
    "空调": [
        ("艾默生", "Liebert PEX+"),
        ("佳力图", "DataMate 3000"),
        ("世图兹", "CyberCool"),
        ("依米康", "SC+"),
    ],
    "KVM": [
        ("力登", "Dominion KX III"),
        ("鸿通", "HT-KVM"),
        ("ATEN", "ACS1216"),
        ("冠林", "GL-KVM"),
    ],
    "PDU": [
        ("克莱沃", "CW-PDU8008"),
        ("突破", "Top-PDU"),
        ("施耐德", "AP8853"),
        ("图腾", "PDU-8"),
    ],
    "其他": [
        ("泛化", "通用监控节点"),
        ("定制", "定制采集器"),
        ("通用", "通用网关"),
    ],
}

# 责任人池
RESP_POOL = [
    "张伟", "王芳", "李强", "刘洋", "陈静", "杨磊",
    "赵敏", "孙浩", "周婷", "吴勇", "郑凯", "冯雪",
]
# 供应商池
VENDOR_POOL = [
    "北京华成科技有限公司",
    "上海联创信息工程有限公司",
    "广州锐捷网络股份有限公司",
    "深圳恒通电子设备有限公司",
    "杭州云栖科技服务有限公司",
    "成都天府运维技术有限公司",
]

ROOMS = ["5-4机房", "3-2机房", "6-1机房", "2-3机房", "7-2机房"]
FAULT_DESC_POOL = [
    "设备指示灯异常，业务间歇性中断",
    "风扇异响，温度报警",
    "电源模块故障导致单机掉电",
    "端口丢包严重，链路抖动",
    "硬盘告警，RAID 降级",
    "固件异常，系统无法启动",
    "内存 ECC 错误频发",
    "散热不足触发降频保护",
]
CHANGE_CONTENT_POOL = [
    "将设备从 R-03 迁移至 R-08，U 位调整",
    "内存由 128G 扩容至 256G",
    "固件版本由 2.1 升级至 2.4",
    "网络端口由万兆切换至光口聚合",
    "新增双电源冗余配置",
]
RETIRE_REASON_POOL = [
    "设备达到使用年限，性能无法满足业务",
    "多次硬件故障，维修成本过高",
    "业务下线，设备闲置待处置",
    "技术淘汰，新一代设备替代",
    "厂家停止维保服务",
]


# ============================ 阶段分布 ============================
# 权重：规划5/在途8/上架10/运行50/维修12/待报废10/已报废5，合计 100
STAGE_WEIGHTS = [
    ("规划", 5),
    ("在途", 8),
    ("上架", 10),
    ("运行", 50),
    ("维修", 12),
    ("待报废", 10),
    ("已报废", 5),
]
STAGES = []
for _stage, _cnt in STAGE_WEIGHTS:
    STAGES.extend([_stage] * _cnt)
assert len(STAGES) == TOTAL_ASSETS, "阶段分布合计必须等于资产总数"
random.shuffle(STAGES)


def build_assets():
    """构造 100 台资产的数据字典列表。"""
    assets = []
    used_sn = set()

    for i in range(TOTAL_ASSETS):
        idx = i + 1
        stage = STAGES[i]
        category = random.choice(CATEGORIES)
        code = CATEGORY_CODE[category]
        asset_code = f"DC-CL-{code}-{idx:04d}"

        brand, model = random.choice(CATEGORY_BRANDS[category])
        device_name = f"{category}-{brand}-{model}"

        # SN：唯一 8 位数字，已报废阶段可留空
        if stage == "已报废":
            sn = None
        else:
            while True:
                cand = "SN" + "".join(random.choice("0123456789") for _ in range(8))
                if cand not in used_sn:
                    used_sn.add(cand)
                    sn = cand
                    break

        # 位置：已报废阶段可留空
        if stage == "已报废":
            room = cabinet = u_position = None
            storage_location = None
        else:
            room = random.choice(ROOMS)
            cabinet_no = random.randint(1, 20)
            cabinet = f"R-{cabinet_no:02d}"
            start_u = random.randint(1, 40)
            u_span = random.choice([1, 2, 4])
            u_position = f"{start_u}-{start_u + u_span - 1}U"
            storage_location = f"{room}-{cabinet}"

        # 入场日期：规划阶段为 None，其余随机 2022-2025
        entry_date = None if stage == "规划" else rand_date(2022, 2025)

        # 责任人：上架/运行/维修必填，其余可空
        responsible_person = (
            random.choice(RESP_POOL) if stage in ("上架", "运行", "维修") else None
        )

        # 维保到期日 / 维保状态
        if stage == "运行":
            warranty_expire_date = future_date(2026, 2028)
            warranty_status = "在保"
        elif stage == "规划":
            warranty_expire_date = None
            warranty_status = random.choice(WARRANTY_STATUSES)
        elif stage == "已报废":
            warranty_expire_date = None
            warranty_status = "无维保"
        else:
            # 非规划非运行非报废：到期日 >= 入场日
            warranty_expire_date = entry_date + timedelta(
                days=random.randint(365, 1825)
            )
            warranty_status = random.choice(WARRANTY_STATUSES)

        # 维保扩展字段
        if stage == "规划":
            int_years = vnd_years = None
            int_start = int_end = vnd_start = vnd_end = None
            int_flag = vnd_flag = "否"
        else:
            int_years = random.randint(1, 5)
            vnd_years = random.randint(1, 5)
            int_start = entry_date
            int_end = entry_date + timedelta(days=int_years * 365)
            vnd_start = entry_date
            vnd_end = entry_date + timedelta(days=vnd_years * 365)
            int_flag = random.choice(["是", "否"])
            vnd_flag = random.choice(["是", "否"])

        config_summary = (
            f"CPU:{random.randint(1, 4) * 8}核 内存:{random.choice([64, 128, 256, 512])}GB "
            f"硬盘:{random.choice([2, 4, 8, 16])}TB 网卡:{random.choice(['万兆', '光口', '千兆'])}"
        )

        assets.append(
            {
                "asset_code": asset_code,
                "asset_category": category,
                "brand": brand,
                "model": model,
                "sn": sn,
                "lifecycle_stage": stage,
                "entry_date": entry_date,
                "responsible_person": responsible_person,
                "warranty_status": warranty_status,
                "warranty_expire_date": warranty_expire_date,
                "asset_category_2": random.choice(["核心区", "普通区", "边界区", "办公区", ""]) or None,
                "room": room,
                "cabinet": cabinet,
                "u_position": u_position,
                "device_name": device_name,
                "project_name": f"机房运维改造项目{random.randint(1, 5)}",
                "project_no": f"P2025-{idx:03d}",
                "size": random.choice(["1U", "2U", "4U", "6U"]),
                "power_consumption": random.randint(100, 5000),
                "ownership": random.choice(OWNERSHIP_TYPES),
                "department": "信息中心",
                "contract_no": f"HT2025-{idx:04d}",
                "config_summary": config_summary,
                "integrator_warranty_years": int_years,
                "integrator_warranty_start": int_start,
                "integrator_warranty_end": int_end,
                "integrator_warranty": int_flag,
                "vendor_warranty_years": vnd_years,
                "vendor_warranty_start": vnd_start,
                "vendor_warranty_end": vnd_end,
                "vendor_warranty": vnd_flag,
                "vendor_contact": random.choice(RESP_POOL),
                "vendor_phone": "1" + "".join(random.choice("0123456789") for _ in range(10)),
                "remarks": random.choice(["", "常规在网运行", "纳入年度巡检计划", "重点关注设备"]),
                "storage_location": storage_location,
            }
        )
    return assets


def main():
    db = SessionLocal()
    try:
        # 显式开启外键约束
        db.execute(text("PRAGMA foreign_keys=ON"))

        # ---- 幂等：先清子表，再清主表 ----
        # 顺序需满足外键依赖：引用 assets 的子表先删，最后删 assets
        db.query(AssetOutbound).delete()
        db.query(AssetInbound).delete()
        db.query(Warranty).delete()
        db.query(Fault).delete()
        db.query(Change).delete()
        db.query(Retirement).delete()
        db.query(Procurement).delete()
        db.query(Asset).delete()
        db.commit()

        assets_data = build_assets()

        # ---- 1) 插入 100 台资产并 flush ----
        # 注意：storage_location 属于 asset_inbound，不属于 assets，构造 Asset 时需剔除
        for a in assets_data:
            asset_kwargs = {k: v for k, v in a.items() if k != "storage_location"}
            db.add(Asset(**asset_kwargs))
        db.flush()

        # 子表单号计数器
        w_seq = f_seq = c_seq = r_seq = o_seq = 0

        # ---- 2) 插入各子表 ----
        for a in assets_data:
            stage = a["lifecycle_stage"]
            code = a["asset_code"]

            # ---- Procurement（每资产 1 条）----
            if a["entry_date"]:
                req_date = a["entry_date"] - timedelta(days=random.randint(15, 200))
                if req_date < date(2022, 1, 1):
                    req_date = date(2022, 1, 1)
            else:
                req_date = rand_date(2022, 2025)
            qty = random.randint(1, 3)
            unit_price = round(random.uniform(5000, 200000), 2)
            proc = Procurement(
                asset_code=code,
                quantity=qty,
                unit_price=unit_price,
                total_price=round(qty * unit_price, 2),
                request_no=f"PR-2025-{a['asset_code'][-4:]}",
                vendor=random.choice(VENDOR_POOL),
                device_name=a["device_name"],
                config_summary=a["config_summary"],
                request_date=req_date,
                applicant=random.choice(RESP_POOL),
                approval_status=random.choice(PROCUREMENT_APPROVAL_STATUSES),
            )
            db.add(proc)

            # ---- AssetInbound（每资产 1 条）----
            if stage in ("上架", "运行", "维修", "待报废", "已报废"):
                inspection = "合格"
            else:
                inspection = random.choice(INBOUND_INSPECTION_RESULTS)
            inbound_date = a["entry_date"] if a["entry_date"] else rand_date(2022, 2025)
            owner_company = "本公司" if a["ownership"] == "自有" else f"客户公司{random.randint(1, 6)}"
            db.add(
                AssetInbound(
                    asset_code=code,
                    inbound_no=f"IB-2025-{a['asset_code'][-4:]}",
                    receive_type=random.choice(RECEIVE_TYPES),
                    ownership=a["ownership"],
                    owner_company=owner_company,
                    asset_category=a["asset_category"],
                    brand=a["brand"],
                    model=a["model"],
                    sn=a["sn"],
                    config_summary=a["config_summary"],
                    purchase_contract_no=a["contract_no"],
                    purchase_total_price=round(random.uniform(5000, 300000), 2),
                    inbound_date=inbound_date,
                    receiver=random.choice(RESP_POOL),
                    inspection_result=inspection,
                    storage_location=a["storage_location"] or "待分配",
                )
            )

            # ---- Warranty（上架/运行/维修 各 1 条）----
            if stage in ("上架", "运行", "维修"):
                w_seq += 1
                base = a["entry_date"] if a["entry_date"] else rand_date(2023, 2024)
                w_start = base
                w_end = base + timedelta(days=random.randint(365, 1095))
                decision_date = w_start + timedelta(days=random.randint(30, 300))
                db.add(
                    Warranty(
                        asset_code=code,
                        warranty_no=f"WT-2025-{w_seq:04d}",
                        warranty_type=random.choice(WARRANTY_TYPES),
                        warranty_vendor=random.choice(VENDOR_POOL),
                        contract_no=f"WBHT-2025-{w_seq:04d}",
                        coverage="整机及主要部件原厂质保与现场技术支持",
                        start_date=w_start,
                        end_date=w_end,
                        renewal_decision=random.choice(RENEWAL_DECISIONS),
                        decision_person=random.choice(RESP_POOL),
                        decision_date=decision_date,
                        cost=round(random.uniform(2000, 80000), 2),
                    )
                )

            # ---- Fault（维修 1-2 条；运行 ~30% 1 条）----
            if stage == "维修":
                fault_n = random.randint(1, 2)
            elif stage == "运行" and random.random() < 0.3:
                fault_n = 1
            else:
                fault_n = 0
            for _ in range(fault_n):
                f_seq += 1
                base = a["entry_date"] if a["entry_date"] else rand_date(2023, 2025)
                fault_date = clamp_past(base + timedelta(days=random.randint(30, 800)))
                if stage == "运行":
                    recovery_date = clamp_past(
                        fault_date + timedelta(days=random.randint(1, 20))
                    )
                else:
                    recovery_date = None  # 维修阶段可空
                db.add(
                    Fault(
                        asset_code=code,
                        fault_no=f"FT-2025-{f_seq:04d}",
                        fault_level=random.choice(FAULT_LEVELS),
                        fault_description=random.choice(FAULT_DESC_POOL),
                        fault_date=fault_date,
                        repair_person=random.choice(RESP_POOL),
                        handle_method=random.choice(HANDLE_METHODS),
                        parts_replaced=random.choice(
                            ["电源模块", "风扇", "硬盘", "内存条", "网卡", None]
                        ),
                        root_cause=random.choice(ROOT_CAUSES),
                        recovery_date=recovery_date,
                        downtime_hours=round(random.uniform(0.5, 72), 1),
                        is_recurring=random.choice([True, False]),
                        repair_cost=round(random.uniform(0, 20000), 2),
                    )
                )

            # ---- Change（运行 ~40% 1 条）----
            if stage == "运行" and random.random() < 0.4:
                c_seq += 1
                exec_date = clamp_past(
                    (a["entry_date"] + timedelta(days=random.randint(60, 900))
                     if a["entry_date"] else rand_date(2023, 2025))
                )
                db.add(
                    Change(
                        asset_code=code,
                        change_type=random.choice(CHANGE_TYPES),
                        work_order_no=f"WO-2025-{c_seq:04d}",
                        change_content=random.choice(CHANGE_CONTENT_POOL),
                        old_config="原配置：内存128G / 固件2.1",
                        new_config="新配置：内存256G / 固件2.4",
                        change_reason=random.choice(
                            ["业务扩容需求", "故障修复后配置调整", "版本统一要求"]
                        ),
                        approver=random.choice(RESP_POOL),
                        executor=random.choice(RESP_POOL),
                        execute_date=exec_date,
                        completion_status=random.choice(COMPLETION_STATUSES),
                    )
                )

            # ---- Retirement（待报废 + 已报废 各 1 条）----
            if stage in ("待报废", "已报废"):
                r_seq += 1
                data_cleared = (
                    "已清除" if stage == "已报废" else random.choice(DATA_CLEAR_OPTIONS)
                )
                appr_date = (
                    a["entry_date"] + timedelta(days=random.randint(400, 1000))
                    if a["entry_date"] else rand_date(2023, 2025)
                )
                uninstall_date = clamp_past(appr_date + timedelta(days=random.randint(5, 60)))
                db.add(
                    Retirement(
                        asset_code=code,
                        retire_reason=random.choice(RETIRE_REASON_POOL),
                        retire_category=random.choice(RETIRE_CATEGORIES),
                        application_no=f"RT-2025-{r_seq:04d}",
                        approver=random.choice(RESP_POOL),
                        approval_date=appr_date,
                        uninstall_date=uninstall_date,
                        uninstall_person=random.choice(RESP_POOL),
                        data_cleared=data_cleared,
                        data_clear_person=random.choice(RESP_POOL),
                        disposal_method=random.choice(DISPOSAL_METHODS),
                        residual_value=round(random.uniform(0, 5000), 2),
                    )
                )

            # ---- AssetOutbound（已报废 各 1 条）----
            if stage == "已报废":
                o_seq += 1
                out_date = clamp_past(
                    (a["entry_date"] + timedelta(days=random.randint(500, 1200))
                     if a["entry_date"] else rand_date(2023, 2025))
                )
                db.add(
                    AssetOutbound(
                        asset_code=code,
                        outbound_no=f"OB-2025-{o_seq:04d}",
                        outbound_reason=random.choice(
                            ["设备报废处置", "回收商拉走处理", "内部拆解后处置"]
                        ),
                        outbound_category="报废",
                        destination=random.choice(
                            ["回收商处理中心", "内部备件库", "报废物资存放区"]
                        ),
                        outbound_date=out_date,
                        receiver_contact=random.choice(RESP_POOL),
                        receiver_phone="1" + "".join(random.choice("0123456789") for _ in range(10)),
                        operator=random.choice(RESP_POOL),
                        approver=random.choice(RESP_POOL),
                    )
                )

        db.commit()

        # ---- 3) 汇总输出 ----
        counts = {
            "assets": db.query(Asset).count(),
            "procurement": db.query(Procurement).count(),
            "asset_inbound": db.query(AssetInbound).count(),
            "asset_outbound": db.query(AssetOutbound).count(),
            "changes": db.query(Change).count(),
            "faults": db.query(Fault).count(),
            "warranties": db.query(Warranty).count(),
            "retirements": db.query(Retirement).count(),
        }
        print("=" * 50)
        print("测试数据生成完成 — 各表记录数汇总")
        print("=" * 50)
        for tbl, cnt in counts.items():
            print(f"  {tbl:>16}: {cnt}")
        print("=" * 50)
        print(f"  资产阶段分布统计:")
        stage_stat = {}
        for a in assets_data:
            stage_stat[a["lifecycle_stage"]] = stage_stat.get(a["lifecycle_stage"], 0) + 1
        for s in LIFECYCLE_STAGES:
            print(f"    {s}: {stage_stat.get(s, 0)}")
        print("=" * 50)

    finally:
        db.close()


if __name__ == "__main__":
    main()
