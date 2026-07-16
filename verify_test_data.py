#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_test_data.py — 全套测试数据完整性验证脚本（可复跑）

独立复核 generate_full_test_data.py 直写 asset_lifecycle.db 产生的 100 台资产
及其全生命周期关联记录，确认数据质量达标。

验证项：
  1) 数量断言（Asset==100；各子表 >= 阈值）
  2) 参照完整性（子表非空 asset_code 必须存在于 assets.asset_code；
     AssetOutbound.asset_code 不得为空）
  3) 枚举合法性（子表枚举字段值 ∈ constants 对应枚举集合）
  4) 校验仪表盘（run_all_checks 的 total_errors==0 且 total_warnings==0）
  5) 日期逻辑（warranty_expire_date >= entry_date；已报废资产 Retirement 记录
     data_cleared=='已清除' 且 application_no 非空）
  6) 资产编号格式（全部 asset_code 匹配 ^DC-CL-[A-Z]{2,4}-\\d{3,4}$，
     依据 SPEC.md DC-CL-[分类码]-[序号] 变长分类码规则）

用法：
  python verify_test_data.py
退出码：全部 PASS 返回 0，否则返回 1。
"""
import os
import re
import sys

# ---- 将 backend 加入 sys.path，复用其 engine / 模型 / 常量 / 校验函数 ----
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(HERE, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import func  # noqa: E402

from database import (  # noqa: E402
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
    PROCUREMENT_APPROVAL_STATUSES,
    RECEIVE_TYPES,
    OUTBOUND_CATEGORIES,
    CHANGE_TYPES,
    FAULT_LEVELS,
    WARRANTY_TYPES,
    DISPOSAL_METHODS,
    DATA_CLEAR_OPTIONS,
)
from validation import run_all_checks  # noqa: E402

# 权威格式见 SPEC.md §1.1：DC-CL-[分类码]-[序号]（分类码为变长大写字母，
# 如 SRV/AC）。业务 schema 校验器(BUG-010)亦允许 [A-Za-z]{2,4}。
# 故分类码取 2~4 位、序号取 3~4 位，覆盖 SPEC 示例(3位)与实测数据(4位)。
ASSET_CODE_RE = re.compile(r"^DC-CL-[A-Z]{2,4}-\d{3,4}$")

# 子表枚举字段 -> 合法枚举集合
ENUM_CHECKS = [
    (Procurement, "approval_status", PROCUREMENT_APPROVAL_STATUSES, "Procurement.approval_status"),
    (AssetInbound, "receive_type", RECEIVE_TYPES, "AssetInbound.receive_type"),
    (AssetOutbound, "outbound_category", OUTBOUND_CATEGORIES, "AssetOutbound.outbound_category"),
    (Change, "change_type", CHANGE_TYPES, "Change.change_type"),
    (Fault, "fault_level", FAULT_LEVELS, "Fault.fault_level"),
    (Warranty, "warranty_type", WARRANTY_TYPES, "Warranty.warranty_type"),
    (Retirement, "disposal_method", DISPOSAL_METHODS, "Retirement.disposal_method"),
    (Retirement, "data_cleared", DATA_CLEAR_OPTIONS, "Retirement.data_cleared"),
]

# 需要检查参照完整性的子表
SUBTABLES = [
    ("Procurement", Procurement),
    ("AssetInbound", AssetInbound),
    ("AssetOutbound", AssetOutbound),
    ("Change", Change),
    ("Fault", Fault),
    ("Warranty", Warranty),
    ("Retirement", Retirement),
]


class Result:
    """单项检查结果"""

    def __init__(self, name, passed, detail=""):
        self.name = name
        self.passed = passed
        self.detail = detail

    def __str__(self):
        tag = "PASS" if self.passed else "FAIL"
        return f"[{tag}] {self.name}" + (f" — {self.detail}" if self.detail else "")


def check_1_counts(db, results):
    """数量断言：Asset==100；子表 >= 阈值"""
    counts = {
        "Asset": db.query(Asset).count(),
        "Procurement": db.query(Procurement).count(),
        "AssetInbound": db.query(AssetInbound).count(),
        "AssetOutbound": db.query(AssetOutbound).count(),
        "Change": db.query(Change).count(),
        "Fault": db.query(Fault).count(),
        "Warranty": db.query(Warranty).count(),
        "Retirement": db.query(Retirement).count(),
    }
    # (表名, 期望值/阈值, 是否严格相等)
    expect = [
        ("Asset", 100, True),
        ("Procurement", 100, False),
        ("AssetInbound", 100, False),
        ("AssetOutbound", 1, False),
        ("Change", 1, False),
        ("Fault", 1, False),
        ("Warranty", 1, False),
        ("Retirement", 1, False),
    ]
    all_ok = True
    details = []
    for name, threshold, strict in expect:
        actual = counts[name]
        ok = (actual == threshold) if strict else (actual >= threshold)
        all_ok = all_ok and ok
        op = "==" if strict else ">="
        details.append(f"{name}={actual}(要求{op}{threshold}){' OK' if ok else ' ✗'}")
    results.append(Result(
        "1.数量断言",
        all_ok,
        "; ".join(details),
    ))
    return counts


def check_2_referential_integrity(db, results):
    """参照完整性：子表非空 asset_code 必须存在于 assets.asset_code；
    AssetOutbound.asset_code 不允许为空"""
    asset_codes = set(
        c[0] for c in db.query(Asset.asset_code)
        .filter(Asset.asset_code != None, Asset.asset_code != "").all()
    )
    all_ok = True
    details = []
    for label, cls in SUBTABLES:
        rows = db.query(cls.asset_code).all()
        codes = [r[0] for r in rows]
        non_null = [c for c in codes if c not in (None, "")]
        orphans = [c for c in non_null if c not in asset_codes]
        null_count = len(codes) - len(non_null)
        if label == "AssetOutbound":
            # AssetOutbound.asset_code 模型定义非空，不得为空
            if null_count > 0:
                all_ok = False
                details.append(f"AssetOutbound 存在{null_count}条空asset_code ✗")
            else:
                details.append("AssetOutbound.asset_code 无空值 OK")
        if orphans:
            all_ok = False
            sample = ", ".join(orphans[:5])
            details.append(f"{label} 存在{len(orphans)}个孤儿编号(样例:{sample}) ✗")
        else:
            details.append(f"{label} 非空编号全部有效({len(non_null)}条) OK")
    results.append(Result(
        "2.参照完整性(外键)",
        all_ok,
        "; ".join(details),
    ))


def check_3_enum_legality(db, results):
    """枚举合法性：子表枚举字段值 ∈ constants 对应枚举集合"""
    all_ok = True
    details = []
    for cls, col, enum_set, label in ENUM_CHECKS:
        col_attr = getattr(cls, col)
        distinct = [r[0] for r in db.query(col_attr)
                    .filter(col_attr != None, col_attr != "").distinct().all()]
        invalid = [v for v in distinct if v not in enum_set]
        if invalid:
            all_ok = False
            sample = ", ".join(map(str, invalid[:5]))
            details.append(f"{label} 非法值[{sample}] 不在枚举集合 ✗")
        else:
            details.append(f"{label} 全部合法({len(distinct)}种取值) OK")
    results.append(Result(
        "3.枚举合法性",
        all_ok,
        "; ".join(details),
    ))


def check_4_dashboard(db, results):
    """校验仪表盘：total_errors==0 且 total_warnings==0"""
    dash = run_all_checks(db)
    ok = (dash.total_errors == 0 and dash.total_warnings == 0)
    details = []
    for c in dash.checks:
        flag = "OK" if c.count == 0 else "✗"
        details.append(f"{c.check_name}:{c.count}({c.severity}){flag}")
    results.append(Result(
        "4.校验仪表盘(run_all_checks)",
        ok,
        f"total_errors={dash.total_errors}, total_warnings={dash.total_warnings}; "
        + "; ".join(details),
    ))
    return dash


def check_5_date_logic(db, results):
    """日期逻辑：(a) warranty_expire_date >= entry_date；
    (b) 已报废资产 Retirement 记录 data_cleared=='已清除' 且 application_no 非空"""
    # (a) Asset 表 warranty_expire_date >= entry_date（两者均有值时）
    bad_date_rows = db.query(Asset).filter(
        Asset.warranty_expire_date != None,
        Asset.entry_date != None,
        Asset.warranty_expire_date < Asset.entry_date,
    ).all()
    a_ok = len(bad_date_rows) == 0

    # (b) 已报废资产对应的 Retirement 记录
    scrap_codes = set(
        c[0] for c in db.query(Asset.asset_code)
        .filter(Asset.lifecycle_stage == "已报废").all()
    )
    ret_for_scrap = db.query(Retirement).filter(
        Retirement.asset_code.in_(scrap_codes)).all() if scrap_codes else []
    b_violations = [
        r for r in ret_for_scrap
        if not (r.data_cleared == "已清除" and (r.application_no not in (None, "")))
    ]
    b_ok = len(b_violations) == 0

    ok = a_ok and b_ok
    details = []
    if a_ok:
        details.append("warranty_expire_date>=entry_date 无违反 OK")
    else:
        sample = ", ".join(a.asset_code for a in bad_date_rows[:5])
        details.append(f"存在{len(bad_date_rows)}条warranty_expire_date<entry_date(样例:{sample}) ✗")
    details.append(
        f"已报废资产Retirement记录{len(ret_for_scrap)}条"
        f"{' data_cleared/单号均合规 OK' if b_ok else ' ✗存在'+str(len(b_violations))+'条违规'}"
    )
    results.append(Result(
        "5.日期逻辑",
        ok,
        "; ".join(details),
    ))


def check_6_asset_code_format(db, results):
    """资产编号格式：全部 asset_code 匹配 ^DC-CL-[A-Z]{2,4}-\\d{3,4}$
    （SPEC.md 定义分类码为变长，空调=AC 2字母合法）"""
    all_codes = []
    all_codes += [c[0] for c in db.query(Asset.asset_code).all()]
    for _, cls in SUBTABLES:
        all_codes += [c[0] for c in db.query(cls.asset_code).all()]
    non_null = [c for c in all_codes if c not in (None, "")]
    bad = [c for c in non_null if not ASSET_CODE_RE.match(c)]
    ok = len(bad) == 0
    pattern = ASSET_CODE_RE.pattern
    if ok:
        details = f"检查{len(non_null)}条非空编号, 全部符合 {pattern} OK"
    else:
        sample = ", ".join(bad[:5])
        details = f"存在{len(bad)}条格式违规(样例:{sample}) ✗"
    results.append(Result(
        "6.资产编号格式",
        ok,
        details,
    ))


def main():
    db = SessionLocal()
    results = []
    try:
        counts = check_1_counts(db, results)
        check_2_referential_integrity(db, results)
        check_3_enum_legality(db, results)
        check_4_dashboard(db, results)
        check_5_date_logic(db, results)
        check_6_asset_code_format(db, results)
    finally:
        db.close()

    # ---- 打印结构化报告 ----
    print("=" * 70)
    print("全套测试数据完整性验证报告 — verify_test_data.py")
    print("=" * 70)
    print("各表实际记录数:")
    for k, v in counts.items():
        print(f"  {k:>14}: {v}")
    print("-" * 70)
    passed = 0
    for r in results:
        print(r)
        if r.passed:
            passed += 1
    print("-" * 70)
    total = len(results)
    all_pass = passed == total
    conclusion = "总体结论: PASS ✅ 全部通过，数据质量达标" if all_pass else \
                 f"总体结论: FAIL ❌ {total - passed}/{total} 项未通过"
    print(conclusion)
    print("=" * 70)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
