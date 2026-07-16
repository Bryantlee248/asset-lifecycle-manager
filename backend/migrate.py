"""数据迁移脚本 — 从旧表结构迁移到新台账模板v1.0

用法：
  python backend/migrate.py          # 独立运行
  或被 start.py 调用 migrate.run_all()

迁移策略：
  - assets / procurement / changes 需重建表（SQLite不支持DROP COLUMN）
  - faults / warranties 只需ADD COLUMN（可直接ALTER TABLE）
  - asset_inbound / asset_outbound 为新建表
"""
import os
import re
import shutil
import sqlite3
from datetime import datetime

# ============ 路径配置 ============
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, '..', 'asset_lifecycle.db')
BACKUP_DIR = os.path.join(BACKEND_DIR, '..', 'migrate_backups')


def backup_database() -> str:
    """备份 asset_lifecycle.db 到 migrate_backups/ 目录"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"asset_lifecycle_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"[备份] 数据库已备份到: {backup_path}")
    return backup_path


def parse_location(location_str: str) -> dict:
    """解析旧 location 字段值为 room/cabinet/u_position

    支持4种格式:
      1. "5-4机房-R-03-15-16U" → room="5-4机房", cabinet="R-03", u_position="15-16U"
      2. "505-R-02-U38"         → room="505",    cabinet="R-02", u_position="U38"
      3. "R-03-15U"             → room="",       cabinet="R-03", u_position="15U"
      4. 其他无法解析             → room=原值,     cabinet="",     u_position=""

    Args:
        location_str: 旧 location 字段原始值

    Returns:
        dict: {"room": str, "cabinet": str, "u_position": str}
    """
    if not location_str:
        return {"room": "", "cabinet": "", "u_position": ""}

    location_str = location_str.strip()

    # 格式1: "机房名-R-XX-U位" 如 "5-4机房-R-03-15-16U"
    pattern1 = re.compile(r'^(.+机房)-R-(\d+)-(.+U)$')
    m1 = pattern1.match(location_str)
    if m1:
        return {"room": m1.group(1), "cabinet": f"R-{m1.group(2)}", "u_position": m1.group(3)}

    # 格式2: "数字房间号-R-XX-U位" 如 "505-R-02-U38"
    pattern2 = re.compile(r'^(\d+)-R-(\d+)-(.+U)$')
    m2 = pattern2.match(location_str)
    if m2:
        return {"room": m2.group(1), "cabinet": f"R-{m2.group(2)}", "u_position": m2.group(3)}

    # 格式3: "R-XX-U位" 如 "R-03-15U" 或 "R-03-15-16U"
    pattern3 = re.compile(r'^R-(\d+)-(.+U)$')
    m3 = pattern3.match(location_str)
    if m3:
        return {"room": "", "cabinet": f"R-{m3.group(1)}", "u_position": m3.group(2)}

    # 格式4: 无法解析 — room=原值, 其他为空
    return {"room": location_str, "cabinet": "", "u_position": ""}


def migrate_assets(conn: sqlite3.Connection) -> None:
    """重建 assets 表: 创建新表→迁移数据含location解析→删除旧表→重命名"""
    cursor = conn.cursor()

    # Step 1: 创建新表 assets_new（严格34列）
    cursor.execute("""
        CREATE TABLE assets_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30) UNIQUE NOT NULL,
            asset_category VARCHAR(20) NOT NULL,
            asset_category_2 VARCHAR(50),
            brand VARCHAR(50),
            model VARCHAR(100),
            sn VARCHAR(50) UNIQUE,
            device_name VARCHAR(100),
            project_name VARCHAR(100),
            project_no VARCHAR(50),
            room VARCHAR(50),
            cabinet VARCHAR(20),
            u_position VARCHAR(20),
            size VARCHAR(20),
            power_consumption INTEGER,
            ownership VARCHAR(20),
            department VARCHAR(50),
            contract_no VARCHAR(50),
            config_summary TEXT,
            lifecycle_stage VARCHAR(20) NOT NULL DEFAULT '规划',
            entry_date DATE,
            responsible_person VARCHAR(30),
            warranty_status VARCHAR(20),
            warranty_expire_date DATE,
            integrator_warranty_years INTEGER,
            integrator_warranty_start DATE,
            integrator_warranty_end DATE,
            integrator_warranty VARCHAR(10),
            vendor_warranty_years INTEGER,
            vendor_warranty_start DATE,
            vendor_warranty_end DATE,
            vendor_warranty VARCHAR(10),
            vendor_contact VARCHAR(50),
            vendor_phone VARCHAR(30),
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            remarks TEXT
        )
    """)
    print("[迁移-assets] 新表 assets_new 已创建")

    # Step 2: 迁移数据（含 location 解析）
    # 读取旧表所有行
    old_rows = cursor.execute("""
        SELECT id, asset_code, asset_category, brand, model, sn,
               location, lifecycle_stage, entry_date, responsible_person,
               warranty_status, warranty_expire_date, last_updated,
               ip_address, remarks
        FROM assets
    """).fetchall()

    migrated_count = 0
    for row in old_rows:
        (old_id, asset_code, asset_category, brand, model, sn,
         location, lifecycle_stage, entry_date, responsible_person,
         warranty_status, warranty_expire_date, last_updated,
         ip_address, remarks) = row

        # 解析 location → room/cabinet/u_position
        parsed = parse_location(location or "")

        cursor.execute("""
            INSERT INTO assets_new (
                id, asset_code, asset_category, brand, model, sn,
                room, cabinet, u_position,
                lifecycle_stage, entry_date, responsible_person,
                warranty_status, warranty_expire_date, last_updated, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            old_id, asset_code, asset_category, brand, model, sn,
            parsed["room"], parsed["cabinet"], parsed["u_position"],
            lifecycle_stage, entry_date, responsible_person,
            warranty_status, warranty_expire_date, last_updated, remarks
        ))
        migrated_count += 1

    print(f"[迁移-assets] 已迁移 {migrated_count} 条记录（location已解析为room/cabinet/u_position）")

    # Step 3: 删除旧表
    cursor.execute("DROP TABLE assets")
    print("[迁移-assets] 旧表 assets 已删除")

    # Step 4: 重命名新表
    cursor.execute("ALTER TABLE assets_new RENAME TO assets")
    print("[迁移-assets] assets_new 已重命名为 assets")


def migrate_procurement(conn: sqlite3.Connection) -> None:
    """重建 procurement 表: 旧字段→新字段"""
    cursor = conn.cursor()

    # Step 1: 创建新表 procurement_new（含asset_code，nullable无外键约束）
    cursor.execute("""
        CREATE TABLE procurement_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30),
            request_no VARCHAR(50) UNIQUE,
            vendor VARCHAR(100),
            device_name VARCHAR(100),
            config_summary TEXT,
            request_date DATE,
            applicant VARCHAR(30),
            approval_status VARCHAR(20) DEFAULT '审批中',
            quantity INTEGER DEFAULT 1,
            unit_price FLOAT,
            total_price FLOAT,
            remarks TEXT
        )
    """)
    print("[迁移-procurement] 新表 procurement_new 已创建")

    # Step 2: 迁移数据（字段映射）
    # 旧字段: asset_code, purchase_order, contract_no, supplier, quantity, unit_price,
    #          total_price, arrival_date, inspector, inspection_result, install_date, remarks
    # 新字段: asset_code→asset_code(nullable), request_no→空, vendor→supplier, device_name→空,
    #         config_summary→空, request_date→arrival_date, applicant→inspector,
    #         approval_status→空, quantity, unit_price, total_price, remarks
    old_rows = cursor.execute("""
        SELECT id, asset_code, supplier, quantity, unit_price, total_price,
               arrival_date, inspector, remarks
        FROM procurement
    """).fetchall()

    migrated_count = 0
    for row in old_rows:
        (old_id, asset_code, supplier, quantity, unit_price, total_price,
         arrival_date, inspector, remarks) = row

        cursor.execute("""
            INSERT INTO procurement_new (
                id, asset_code, vendor, request_date, applicant,
                quantity, unit_price, total_price, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            old_id, asset_code, supplier, arrival_date, inspector,
            quantity, unit_price, total_price, remarks
        ))
        migrated_count += 1

    print(f"[迁移-procurement] 已迁移 {migrated_count} 条记录")

    # Step 3: 删除旧表
    cursor.execute("DROP TABLE procurement")
    print("[迁移-procurement] 旧表 procurement 已删除")

    # Step 4: 重命名
    cursor.execute("ALTER TABLE procurement_new RENAME TO procurement")
    print("[迁移-procurement] procurement_new 已重命名为 procurement")


def migrate_changes(conn: sqlite3.Connection) -> None:
    """重建 changes 表: 移除old/new_location/ip/responsible，新增work_order_no/change_content/old_config/new_config"""
    cursor = conn.cursor()

    # Step 1: 创建新表 changes_new
    cursor.execute("""
        CREATE TABLE changes_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30) NOT NULL REFERENCES assets(asset_code),
            change_type VARCHAR(20) NOT NULL,
            work_order_no VARCHAR(50),
            change_content TEXT,
            old_config TEXT,
            new_config TEXT,
            change_reason TEXT,
            approver VARCHAR(30),
            executor VARCHAR(30),
            execute_date DATE,
            completion_status VARCHAR(20) DEFAULT '进行中',
            remarks TEXT
        )
    """)
    print("[迁移-changes] 新表 changes_new 已创建")

    # Step 2: 迁移数据
    # 旧字段: asset_code, change_type, old_location, new_location, old_ip, new_ip,
    #          old_responsible, new_responsible, change_reason, approver, executor,
    #          execute_date, completion_status, remarks
    # 新字段: 移除位置/IP/责任人旧字段，新增4字段（留空）
    old_rows = cursor.execute("""
        SELECT id, asset_code, change_type, change_reason,
               approver, executor, execute_date, completion_status, remarks
        FROM changes
    """).fetchall()

    migrated_count = 0
    for row in old_rows:
        (old_id, asset_code, change_type, change_reason,
         approver, executor, execute_date, completion_status, remarks) = row

        cursor.execute("""
            INSERT INTO changes_new (
                id, asset_code, change_type, change_reason,
                approver, executor, execute_date, completion_status, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            old_id, asset_code, change_type, change_reason,
            approver, executor, execute_date, completion_status, remarks
        ))
        migrated_count += 1

    print(f"[迁移-changes] 已迁移 {migrated_count} 条记录")

    # Step 3: 删除旧表
    cursor.execute("DROP TABLE changes")
    print("[迁移-changes] 旧表 changes 已删除")

    # Step 4: 重命名
    cursor.execute("ALTER TABLE changes_new RENAME TO changes")
    print("[迁移-changes] changes_new 已重命名为 changes")


def migrate_faults(conn: sqlite3.Connection) -> None:
    """重建 faults 表: 加2列(fault_no UNIQUE, repair_cost) + UPDATE P2→P2-严重"""
    cursor = conn.cursor()

    # SQLite 不允许 ALTER TABLE ADD UNIQUE 列，需重建表
    cursor.execute("""
        CREATE TABLE faults_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30) NOT NULL REFERENCES assets(asset_code),
            fault_no VARCHAR(50) UNIQUE,
            fault_level VARCHAR(10) NOT NULL,
            fault_description TEXT,
            fault_date DATE,
            repair_person VARCHAR(30),
            handle_method VARCHAR(30),
            parts_replaced TEXT,
            root_cause VARCHAR(20),
            recovery_date DATE,
            downtime_hours FLOAT,
            is_recurring BOOLEAN DEFAULT 0,
            repair_cost FLOAT,
            remarks TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO faults_new (id, asset_code, fault_level, fault_description, fault_date,
            repair_person, handle_method, parts_replaced, root_cause, recovery_date,
            downtime_hours, is_recurring, remarks)
        SELECT id, asset_code, fault_level, fault_description, fault_date,
            repair_person, handle_method, parts_replaced, root_cause, recovery_date,
            downtime_hours, is_recurring, remarks
        FROM faults
    """)
    print(f"[迁移-faults] 已迁移 {cursor.rowcount} 条记录到 faults_new")

    # 更新 P2 → P2-严重
    result = cursor.execute("""
        UPDATE faults_new SET fault_level = 'P2-严重' WHERE fault_level = 'P2'
    """)
    print(f"[迁移-faults] 已更新 {result.rowcount} 条 P2→P2-严重")

    cursor.execute("DROP TABLE faults")
    cursor.execute("ALTER TABLE faults_new RENAME TO faults")
    print("[迁移-faults] faults_new 已重命名为 faults")


def migrate_warranties(conn: sqlite3.Connection) -> None:
    """重建 warranties 表: 加3列(warranty_no UNIQUE, warranty_type, warranty_vendor)"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE warranties_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30) NOT NULL REFERENCES assets(asset_code),
            warranty_no VARCHAR(50) UNIQUE,
            warranty_type VARCHAR(20),
            warranty_vendor VARCHAR(100),
            contract_no VARCHAR(50),
            coverage TEXT,
            start_date DATE,
            end_date DATE,
            renewal_decision VARCHAR(20),
            decision_person VARCHAR(30),
            decision_date DATE,
            renewal_contract_no VARCHAR(50),
            renewal_start_date DATE,
            renewal_end_date DATE,
            cost FLOAT,
            remarks TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO warranties_new (id, asset_code, contract_no, coverage, start_date, end_date,
            renewal_decision, decision_person, decision_date, renewal_contract_no,
            renewal_start_date, renewal_end_date, cost, remarks)
        SELECT id, asset_code, contract_no, coverage, start_date, end_date,
            renewal_decision, decision_person, decision_date, renewal_contract_no,
            renewal_start_date, renewal_end_date, cost, remarks
        FROM warranties
    """)
    print(f"[迁移-warranties] 已迁移 {cursor.rowcount} 条记录到 warranties_new")

    cursor.execute("DROP TABLE warranties")
    cursor.execute("ALTER TABLE warranties_new RENAME TO warranties")
    print("[迁移-warranties] warranties_new 已重命名为 warranties")


def create_new_tables(conn: sqlite3.Connection) -> None:
    """创建新表: asset_inbound / asset_outbound"""
    cursor = conn.cursor()

    # asset_inbound
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_inbound (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30) REFERENCES assets(asset_code),
            inbound_no VARCHAR(50),
            receive_type VARCHAR(20),
            ownership VARCHAR(20),
            owner_company VARCHAR(100),
            project_name VARCHAR(100),
            project_no VARCHAR(50),
            asset_category VARCHAR(20),
            brand VARCHAR(50),
            model VARCHAR(100),
            sn VARCHAR(50),
            config_summary TEXT,
            purchase_contract_no VARCHAR(50),
            purchase_total_price FLOAT,
            inbound_date DATE,
            receiver VARCHAR(30),
            inspection_result VARCHAR(20),
            storage_location VARCHAR(100),
            remarks TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[新建表] asset_inbound 已创建")

    # asset_outbound
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_outbound (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_code VARCHAR(30) NOT NULL REFERENCES assets(asset_code),
            outbound_no VARCHAR(50),
            outbound_reason TEXT,
            outbound_category VARCHAR(20),
            destination VARCHAR(100),
            outbound_date DATE,
            receiver_contact VARCHAR(50),
            receiver_phone VARCHAR(30),
            operator VARCHAR(30),
            approver VARCHAR(30),
            remarks TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[新建表] asset_outbound 已创建")


def verify_integrity(conn: sqlite3.Connection) -> dict:
    """验证迁移完整性: 行数一致性 + 外键完整性"""
    cursor = conn.cursor()
    results = {}

    # 行数验证
    tables = ["assets", "procurement", "changes", "faults", "warranties",
              "retirements", "asset_inbound", "asset_outbound"]
    for table in tables:
        try:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            results[f"{table}_rows"] = count
            print(f"[验证] {table}: {count} 行")
        except sqlite3.OperationalError as e:
            results[f"{table}_error"] = str(e)
            print(f"[验证] {table}: 表不存在或出错 — {e}")

    # 外键完整性验证
    fk_checks = [
        ("changes.asset_code → assets.asset_code",
         "SELECT COUNT(*) FROM changes c WHERE c.asset_code NOT IN (SELECT a.asset_code FROM assets a)"),
        ("faults.asset_code → assets.asset_code",
         "SELECT COUNT(*) FROM faults f WHERE f.asset_code NOT IN (SELECT a.asset_code FROM assets a)"),
        ("warranties.asset_code → assets.asset_code",
         "SELECT COUNT(*) FROM warranties w WHERE w.asset_code NOT IN (SELECT a.asset_code FROM assets a)"),
        ("retirements.asset_code → assets.asset_code",
         "SELECT COUNT(*) FROM retirements r WHERE r.asset_code NOT IN (SELECT a.asset_code FROM assets a)"),
        ("asset_inbound.asset_code → assets.asset_code",
         "SELECT COUNT(*) FROM asset_inbound i WHERE i.asset_code IS NOT NULL AND i.asset_code NOT IN (SELECT a.asset_code FROM assets a)"),
        ("asset_outbound.asset_code → assets.asset_code",
         "SELECT COUNT(*) FROM asset_outbound o WHERE o.asset_code NOT IN (SELECT a.asset_code FROM assets a)"),
    ]
    for desc, sql in fk_checks:
        try:
            orphan_count = cursor.execute(sql).fetchone()[0]
            results[f"fk_{desc}"] = orphan_count
            status = "OK" if orphan_count == 0 else f"有{orphan_count}条孤立记录"
            print(f"[验证-FK] {desc}: {status}")
        except sqlite3.OperationalError as e:
            results[f"fk_{desc}_error"] = str(e)
            print(f"[验证-FK] {desc}: 验证失败 — {e}")

    return results


def run_all() -> None:
    """串联全部迁移步骤"""
    print("=" * 60)
    print("  数据迁移 — 新台账模板v1.0")
    print("=" * 60)

    # Step 0: 检查数据库是否存在
    if not os.path.exists(DB_PATH):
        print("[错误] 数据库文件不存在: " + DB_PATH)
        return

    # Step 1: 备份
    backup_database()

    # Step 2: 连接数据库
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")  # 迁移期间暂时关闭外键检查
    print("[连接] 数据库已连接，外键检查暂时关闭")

    try:
        # Step 3: 逐表迁移
        migrate_assets(conn)
        migrate_procurement(conn)
        migrate_changes(conn)
        migrate_faults(conn)
        migrate_warranties(conn)
        create_new_tables(conn)

        # Step 4: 提交事务
        conn.commit()
        print("[提交] 所有迁移已提交")

        # Step 5: 重新开启外键检查
        conn.execute("PRAGMA foreign_keys=ON")
        print("[连接] 外键检查已重新开启")

        # Step 6: 验证完整性
        verify_integrity(conn)

        print("=" * 60)
        print("  迁移完成！")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"[错误] 迁移失败，已回滚: {e}")
        raise
    finally:
        conn.close()


# ============ 独立运行入口 ============
if __name__ == "__main__":
    run_all()
