"""历史阶段时间线回填脚本 — 报表统计模块 P2（S-16/S-17 数据底座）

对现有资产按已知日期字段推演出一条「合理」的阶段时间线，写入 asset_stage_log（is_backfill=True）。
回填结果为推演值，仅用于趋势/对比图立即可见，不代表真实历史事件。

运行方式：
    python backend/backfill_stage_log.py

特性：
    - 运行前自动备份共享库 asset_lifecycle.db 到 migrate_backups/（同名 + .bak + 时间戳）
    - 幂等：先 DELETE 现有 is_backfill=True 记录，再写入
    - 通过 database.py 的 Base.metadata.create_all 确保 asset_stage_log 表存在
    - 逐资产收集锚点 → 按日期升序 + 单调不回退夹断 → 生成相邻锚点间的阶段变更记录 → 收尾补当前阶段
"""
import os
import shutil
from datetime import date, datetime, time

from database import (
    Base, engine, SessionLocal,
    Asset, AssetStageLog, Fault, Retirement, AssetOutbound, AssetInbound,
    record_stage_change,
)
from constants import LIFECYCLE_STAGES


# 共享库路径（与 database.py 的 DATABASE_URL 保持一致：backend/../asset_lifecycle.db）
_DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DB_DIR, "..", "asset_lifecycle.db")
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "migrate_backups")

STAGE_ORDER = LIFECYCLE_STAGES  # 规划 < 在途 < 上架 < 运行 < 维修 < 待报废 < 已报废


def _stage_index(stage: str) -> int:
    """返回阶段在 7 阶段顺序中的下标；未知阶段返回 -1"""
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1


def backup_database() -> str:
    """备份共享库到 migrate_backups/，返回备份文件路径"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"asset_lifecycle.db.bak_{ts}")
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def _collect_anchors(db, asset) -> list:
    """收集单资产的阶段锚点列表 [(date, to_stage), ...]"""
    anchors = []

    # 0) 出生：entry_date / AssetInbound.inbound_date / 兜底 规划(2000-01-01)
    birth_date = asset.entry_date
    if not birth_date:
        inbound = db.query(AssetInbound).filter(AssetInbound.asset_code == asset.asset_code).first()
        if inbound and inbound.inbound_date:
            birth_date = inbound.inbound_date
    if birth_date:
        anchors.append((birth_date, "上架"))
    else:
        anchors.append((date(2000, 1, 1), "规划"))

    # 1) 故障：fault_date→维修；recovery_date≥fault_date 追加 运行
    faults = db.query(Fault).filter(Fault.asset_code == asset.asset_code).all()
    for f in faults:
        if f.fault_date:
            anchors.append((f.fault_date, "维修"))
            if f.recovery_date and f.recovery_date >= f.fault_date:
                anchors.append((f.recovery_date, "运行"))

    # 2) 待报废：Retirement.approval_date
    # 3) 已报废：Retirement.uninstall_date（无 Retirement 记录则用 AssetOutbound.outbound_date）
    ret = db.query(Retirement).filter(Retirement.asset_code == asset.asset_code).first()
    if ret:
        if ret.approval_date:
            anchors.append((ret.approval_date, "待报废"))
        if ret.uninstall_date:
            anchors.append((ret.uninstall_date, "已报废"))
    else:
        outbound = db.query(AssetOutbound).filter(AssetOutbound.asset_code == asset.asset_code).first()
        if outbound and outbound.outbound_date:
            anchors.append((outbound.outbound_date, "已报废"))

    return anchors


def _build_asset_logs(db, asset) -> list:
    """基于锚点推演该资产的阶段变更记录（含单调夹断 + 收尾当前阶段），返回 [(date, from, to), ...]"""
    anchors = _collect_anchors(db, asset)
    # 按 (日期升序, 阶段升序) 排序：同日期多锚点取最靠后阶段
    anchors.sort(key=lambda x: (x[0], _stage_index(x[1]) if _stage_index(x[1]) >= 0 else 0))

    records = []
    prev_idx = 0  # 初始阶段：规划
    for d, to_stage in anchors:
        idx = _stage_index(to_stage)
        if idx < 0:
            idx = prev_idx
        clamped_idx = max(prev_idx, idx)  # 强制单调不回退
        clamped_stage = STAGE_ORDER[clamped_idx]
        if clamped_stage != STAGE_ORDER[prev_idx]:
            records.append((d, STAGE_ORDER[prev_idx], clamped_stage))
        prev_idx = clamped_idx

    # 收尾：末态 = 当前 lifecycle_stage（强制，使「现在」与时间线末端一致）
    current = asset.lifecycle_stage
    current_idx = _stage_index(current)
    if current_idx < 0:
        current_idx = prev_idx
        current = STAGE_ORDER[current_idx]
    if current_idx != prev_idx:
        # 用当日 23:59:59 确保严格晚于所有锚点（锚点为 00:00:00），避免同日期并列歧义
        tail_dt = datetime.combine(date.today(), time(23, 59, 59))
        records.append((tail_dt, STAGE_ORDER[prev_idx], current))
        prev_idx = current_idx

    return records


def run() -> dict:
    """执行回填，返回统计信息"""
    # 确保表存在
    Base.metadata.create_all(bind=engine)

    # 1) 备份
    backup_path = backup_database()

    db = SessionLocal()
    try:
        # 2) 幂等：先清除旧回填记录
        deleted = db.query(AssetStageLog).filter(AssetStageLog.is_backfill == True).delete()
        db.commit()

        # 3) 逐资产推演并写入
        assets = db.query(Asset).all()
        total_assets = len(assets)
        written = 0
        for asset in assets:
            for d, from_stage, to_stage in _build_asset_logs(db, asset):
                changed_at = datetime.combine(d, time.min) if isinstance(d, date) and not isinstance(d, datetime) else d
                record_stage_change(
                    db, asset.asset_code, from_stage, to_stage,
                    changed_at, operator="system_backfill",
                    reason="历史推演回填", is_backfill=True
                )
                written += 1
        db.commit()

        # 4) 校验：每月末 Σcounts 是否 = 总资产数
        from reports_stats import get_stage_trend
        trend = get_stage_trend(db, months=12)
        month_totals = {row["month"]: row["total"] for row in trend["matrix"]}
        mismatched = {m: t for m, t in month_totals.items() if t != total_assets}

        return {
            "backup_path": backup_path,
            "deleted_old_backfill": deleted,
            "total_assets": total_assets,
            "written_records": written,
            "is_backfill": trend["is_backfill"],
            "month_totals": month_totals,
            "mismatched_months": mismatched,
        }
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("历史阶段时间线回填（asset_stage_log）")
    print("=" * 60)
    result = run()
    print(f"备份文件      : {result['backup_path']}")
    print(f"清除旧回填    : {result['deleted_old_backfill']} 行")
    print(f"总资产数      : {result['total_assets']}")
    print(f"本次写入记录  : {result['written_records']} 行")
    print(f"is_backfill   : {result['is_backfill']}")
    print("-" * 60)
    print("每月末资产总数（趋势口径，期望值=总资产数）：")
    for m, t in result["month_totals"].items():
        flag = "  ✔" if t == result["total_assets"] else "  ⚠(该月前存在未建档资产，属正常)"
        print(f"  {m}: {t}{flag}")
    if result["mismatched_months"]:
        print("说明：上述 ⚠ 月份总数 < 总资产数，通常因部分资产建档日期晚于该月，属推演预期。")
    print("=" * 60)
    print("回填完成。")
