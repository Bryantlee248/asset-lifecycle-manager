from sqlalchemy import func


def test_scenario_seed_adds_fifty_assets_without_touching_existing_data(isolated_runtime):
    from database import (
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
    from generate_scenario_test_data import SCENARIO_PREFIX, seed_scenario_test_data

    db = SessionLocal()
    try:
        db.add(Asset(asset_code="DC-CL-OLD-001", asset_category="服务器"))
        db.commit()

        summary = seed_scenario_test_data(db)

        assert summary["assets_created"] == 50
        assert db.query(Asset).filter(Asset.asset_code == "DC-CL-OLD-001").count() == 1
        assert db.query(Asset).filter(Asset.asset_code.like(f"{SCENARIO_PREFIX}%")).count() == 50
        assert db.query(Procurement).filter(Procurement.request_no.like("SIM-PR-%")).count() == 12
        assert db.query(AssetInbound).filter(AssetInbound.inbound_no.like("SIM-IB-%")).count() == 38
        assert db.query(Warranty).filter(Warranty.warranty_no.like("SIM-WT-%")).count() == 15
        assert db.query(Fault).filter(Fault.fault_no.like("SIM-FT-%")).count() == 9
        assert db.query(Change).filter(Change.work_order_no.like("SIM-CH-%")).count() == 3
        assert db.query(Retirement).filter(Retirement.application_no.like("SIM-RT-%")).count() == 3
        assert db.query(AssetOutbound).filter(AssetOutbound.outbound_no.like("SIM-OB-%")).count() == 1

        stage_counts = dict(
            db.query(Asset.lifecycle_stage, func.count(Asset.id))
            .filter(Asset.asset_code.like(f"{SCENARIO_PREFIX}%"))
            .group_by(Asset.lifecycle_stage)
            .all()
        )
        assert stage_counts == {
            "规划": 6,
            "在途": 6,
            "上架": 8,
            "运行": 18,
            "维修": 9,
            "待报废": 2,
            "已报废": 1,
        }

        repeated = seed_scenario_test_data(db)
        assert repeated["assets_created"] == 0
        assert db.query(Asset).filter(Asset.asset_code.like(f"{SCENARIO_PREFIX}%")).count() == 50
    finally:
        db.close()
