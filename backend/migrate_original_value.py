"""原值迁移与回填脚本 — 报表统计模块（方案A）

为 Asset 表新增 original_value 列，并从 Procurement 按 asset_code 聚合 total_price 回填。
运行前自动备份 asset_lifecycle.db，脚本可重复运行（幂等）。

用法：
  python backend/migrate_original_value.py
"""
import os
import shutil
import sqlite3
from datetime import datetime

# ============ 路径配置 ============
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, '..', 'asset_lifecycle.db')
BACKUP_DIR = os.path.join(BACKEND_DIR, '..', 'migrate_backups')


def backup_database() -> str:
    """备份 asset_lifecycle.db 到 migrate_backups/ 目录（同名+.bak+时间戳）"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"asset_lifecycle_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"[备份] 数据库已备份到: {backup_path}")
    return backup_path


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """检查表中是否已存在指定列"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    # PRAGMA table_info 返回行: (cid, name, type, notnull, dflt_value, pk)
    return any(row[1] == column for row in rows)


def run() -> None:
    """执行迁移：备份 → 新增列 → 按 asset_code 回填原值 → 校验"""
    print("=" * 60)
    print("  原值迁移 — 报表统计模块(方案A)")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"[错误] 数据库文件不存在: {DB_PATH}")
        return

    # Step 1: 备份
    backup_database()

    # Step 2: 直连数据库（迁移期间关闭外键检查）
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")
    print("[连接] 数据库已连接，外键检查暂时关闭")

    try:
        # Step 3: 若列不存在则新增（数据库模型已含该列时，create_all 会先建好，此处自动跳过）
        if not column_exists(conn, "assets", "original_value"):
            conn.execute("ALTER TABLE assets ADD COLUMN original_value FLOAT DEFAULT 0.0")
            print("[迁移] assets 表已新增 original_value 列")
        else:
            print("[迁移] original_value 列已存在，跳过 ALTER TABLE")

        # Step 4: 按 asset_code 回填原值 = SUM(total_price)
        # 仅对「有采购记录且 asset_code 非空」的资产回填；无记录 / 空 code 的资产保持 0.0（DEFAULT 已覆盖）
        update_sql = """
            UPDATE assets
            SET original_value = COALESCE(
                (SELECT SUM(total_price) FROM procurement p WHERE p.asset_code = assets.asset_code),
                0.0
            )
            WHERE asset_code IN (SELECT DISTINCT asset_code FROM procurement WHERE asset_code IS NOT NULL)
        """
        cur = conn.execute(update_sql)
        updated_rows = cur.rowcount
        conn.commit()
        print(f"[回填] 已按 asset_code 回填原值，影响资产行数: {updated_rows}")

        # Step 5: 重新开启外键检查
        conn.execute("PRAGMA foreign_keys=ON")
        print("[连接] 外键检查已重新开启")

        # Step 6: 校验 — 统计已回填(>0)与总计
        total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        filled = conn.execute("SELECT COUNT(*) FROM assets WHERE original_value > 0").fetchone()[0]
        total_value = conn.execute("SELECT COALESCE(SUM(original_value), 0) FROM assets").fetchone()[0]
        procurement_sum = conn.execute("SELECT COALESCE(SUM(total_price), 0) FROM procurement").fetchone()[0]
        print("-" * 60)
        print(f"[校验] 资产总数: {total_assets}")
        print(f"[校验] 原值>0 的资产数: {filled}")
        print(f"[校验] 资产原值合计: {round(float(total_value), 2)} 元")
        print(f"[校验] 采购总额(PROCUREMENT): {round(float(procurement_sum), 2)} 元")
        print("=" * 60)
        print("  迁移完成！请重启后端使 ORM 模型与库表列对齐。")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"[错误] 迁移失败，已回滚: {e}")
        raise
    finally:
        conn.close()


# ============ 独立运行入口 ============
if __name__ == "__main__":
    run()
