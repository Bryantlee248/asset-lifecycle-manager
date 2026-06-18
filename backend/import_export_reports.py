"""批量导入导出与报表统计API模块"""
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from fastapi import UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date, timedelta, datetime
from typing import Optional
from urllib.parse import quote

from database import get_db, Asset, Procurement, Change, Fault, Warranty, Retirement
from constants import (
    CATEGORIES, LIFECYCLE_STAGES, WARRANTY_STATUSES, INSPECTION_RESULTS,
    CHANGE_TYPES, FAULT_LEVELS, HANDLE_METHODS, ROOT_CAUSES,
    RENEWAL_DECISIONS, RETIRE_CATEGORIES, DATA_CLEAR_OPTIONS, COMPLETION_STATUSES
)


# ============ 下拉选项校验映射 ============
VALID_OPTIONS = {
    "asset_category": CATEGORIES,
    "lifecycle_stage": LIFECYCLE_STAGES,
    "warranty_status": WARRANTY_STATUSES,
    "inspection_result": INSPECTION_RESULTS,
    "change_type": CHANGE_TYPES,
    "fault_level": FAULT_LEVELS,
    "handle_method": HANDLE_METHODS,
    "root_cause": ROOT_CAUSES,
    "renewal_decision": RENEWAL_DECISIONS,
    "retire_category": RETIRE_CATEGORIES,
    "data_cleared": DATA_CLEAR_OPTIONS,
    "completion_status": COMPLETION_STATUSES,
}


def validate_field(field_name: str, value: str) -> list[str]:
    """校验字段值是否在合法选项内，返回错误列表"""
    errors = []
    if field_name in VALID_OPTIONS and value:
        if value not in VALID_OPTIONS[field_name]:
            errors.append(f"字段'{field_name}'值'{value}'不在合法选项中: {VALID_OPTIONS[field_name]}")
    return errors


# ============ 批量导入 ============
async def import_assets_excel(file: UploadFile, db: Session):
    """批量导入资产台账数据（Excel文件）"""
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content))
    ws = wb.active

    # 读取表头
    headers = []
    for cell in ws[1]:
        headers.append(str(cell.value).strip() if cell.value else "")

    # 期望的列名映射
    expected_cols = {
        "资产编号": "asset_code", "资产分类": "asset_category", "品牌": "brand",
        "型号": "model", "SN号": "sn", "位置": "location",
        "生命周期阶段": "lifecycle_stage", "入场日期": "entry_date",
        "责任人": "responsible_person", "维保状态": "warranty_status",
        "维保到期日": "warranty_expire_date", "IP地址": "ip_address", "备注": "remarks"
    }

    col_map = {}
    for i, h in enumerate(headers):
        if h in expected_cols:
            col_map[expected_cols[h]] = i

    # 必须有资产编号和分类列
    if "asset_code" not in col_map or "asset_category" not in col_map:
        raise HTTPException(400, "Excel缺少必要列：资产编号、资产分类")

    success_count = 0
    skip_count = 0
    errors = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[col_map.get("asset_code", 0)]:
            continue

        data = {}
        for field, col_idx in col_map.items():
            val = row[col_idx] if col_idx < len(row) else None
            if val is not None:
                if isinstance(val, datetime):
                    data[field] = val.strftime("%Y-%m-%d")
                elif isinstance(val, date):
                    data[field] = val.strftime("%Y-%m-%d")
                else:
                    data[field] = str(val).strip()

        # 字段校验
        row_errors = []
        for field, value in data.items():
            row_errors.extend(validate_field(field, value))

        # 检查编号唯一性
        code = data.get("asset_code", "")
        existing = db.query(Asset).filter(Asset.asset_code == code).first()
        if existing:
            skip_count += 1
            errors.append(f"行{row_idx}: 编号{code}已存在，跳过")
            continue

        if row_errors:
            errors.append(f"行{row_idx}: {'; '.join(row_errors)}")
            continue

        # 必填字段默认值
        if "lifecycle_stage" not in data:
            data["lifecycle_stage"] = "规划"

        try:
            asset = Asset(**data)
            db.add(asset)
            success_count += 1
            # 每100行提交一次
            if success_count % 100 == 0:
                db.commit()
        except Exception as e:
            db.rollback()
            errors.append(f"行{row_idx}: 写入失败 - {str(e)}")

    # 提交剩余的记录
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"批量提交失败 - {str(e)}")

    return {
        "success": success_count,
        "skipped": skip_count,
        "errors": errors[:50],
        "total_rows": ws.max_row - 1
    }


async def import_subtable_excel(file: UploadFile, table_type: str, db: Session):
    """批量导入分表数据（采购/变更/故障/维保/退役）"""
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content))
    ws = wb.active

    model_map = {
        "procurement": (Procurement, {
            "资产编号": "asset_code", "采购单号": "purchase_order", "合同号": "contract_no",
            "供应商": "supplier", "数量": "quantity", "单价": "unit_price",
            "总价": "total_price", "到货日期": "arrival_date", "验收人": "inspector",
            "验收结果": "inspection_result", "上架日期": "install_date", "备注": "remarks"
        }),
        "change": (Change, {
            "资产编号": "asset_code", "变更类型": "change_type", "原位置": "old_location",
            "新位置": "new_location", "原IP": "old_ip", "新IP": "new_ip",
            "原责任人": "old_responsible", "新责任人": "new_responsible",
            "变更原因": "change_reason", "审批人": "approver", "执行人": "executor",
            "执行日期": "execute_date", "完成状态": "completion_status", "备注": "remarks"
        }),
        "fault": (Fault, {
            "资产编号": "asset_code", "故障等级": "fault_level", "故障现象": "fault_description",
            "故障日期": "fault_date", "维修人": "repair_person", "处理方式": "handle_method",
            "配件更换": "parts_replaced", "根因分类": "root_cause", "恢复日期": "recovery_date",
            "停机时长": "downtime_hours", "是否复发": "is_recurring", "备注": "remarks"
        }),
        "warranty": (Warranty, {
            "资产编号": "asset_code", "合同编号": "contract_no", "覆盖范围": "coverage",
            "维保起始日": "start_date", "维保到期日": "end_date", "续保决策": "renewal_decision",
            "决策人": "decision_person", "决策日期": "decision_date",
            "续保合同号": "renewal_contract_no", "续保起始日": "renewal_start_date",
            "续保到期日": "renewal_end_date", "维保费用": "cost", "备注": "remarks"
        }),
        "retirement": (Retirement, {
            "资产编号": "asset_code", "报废原因": "retire_reason", "报废类别": "retire_category",
            "申请单号": "application_no", "审批人": "approver", "审批日期": "approval_date",
            "下架日期": "uninstall_date", "下架人": "uninstall_person",
            "数据清除确认": "data_cleared", "数据清除人": "data_clear_person",
            "处置方式": "disposal_method", "残值回收": "residual_value", "备注": "remarks"
        }),
    }

    if table_type not in model_map:
        raise HTTPException(400, f"不支持的表类型: {table_type}")

    Model, col_mapping = model_map[table_type]

    headers = [str(cell.value).strip() if cell.value else "" for cell in ws[1]]
    col_map = {}
    for i, h in enumerate(headers):
        if h in col_mapping:
            col_map[col_mapping[h]] = i

    if "asset_code" not in col_map:
        raise HTTPException(400, "Excel缺少必要列：资产编号")

    success_count = 0
    errors = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[col_map.get("asset_code", 0)]:
            continue

        data = {}
        for field, col_idx in col_map.items():
            val = row[col_idx] if col_idx < len(row) else None
            if val is not None:
                if isinstance(val, datetime):
                    data[field] = val.strftime("%Y-%m-%d")
                elif isinstance(val, date):
                    data[field] = val.strftime("%Y-%m-%d")
                elif field in ("quantity", "unit_price", "total_price", "downtime_hours", "cost", "residual_value"):
                    try:
                        data[field] = float(val)
                        if field == "quantity":
                            data[field] = int(data[field])
                    except (ValueError, TypeError):
                        data[field] = None
                elif field == "is_recurring":
                    data[field] = str(val).strip() in ("是", "True", "true", "1", "复发")
                else:
                    data[field] = str(val).strip()

        # 校验
        row_errors = []
        for field, value in data.items():
            if isinstance(value, str):
                row_errors.extend(validate_field(field, value))

        if row_errors:
            errors.append(f"行{row_idx}: {'; '.join(row_errors)}")
            continue

        try:
            item = Model(**data)
            db.add(item)
            # P1/P2故障自动切换主表阶段
            if table_type == "fault" and data.get("fault_level") in ("P1", "P2"):
                asset = db.query(Asset).filter(Asset.asset_code == data.get("asset_code")).first()
                if asset and asset.lifecycle_stage in ["运行", "上架"]:
                    asset.lifecycle_stage = "维修"
            success_count += 1
            # 每100行提交一次
            if success_count % 100 == 0:
                db.commit()
        except Exception as e:
            db.rollback()
            errors.append(f"行{row_idx}: 写入失败 - {str(e)}")

    # 提交剩余的记录
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"批量提交失败 - {str(e)}")

    return {"success": success_count, "errors": errors[:50], "total_rows": ws.max_row - 1}


# ============ 批量导出 ============
def export_assets_excel(
    db: Session,
    category: Optional[str] = None,
    stage: Optional[str] = None,
    warranty_status: Optional[str] = None,
    search: Optional[str] = None
) -> StreamingResponse:
    """导出资产台账为Excel文件"""
    query = db.query(Asset)
    if category:
        query = query.filter(Asset.asset_category == category)
    if stage:
        query = query.filter(Asset.lifecycle_stage == stage)
    if warranty_status:
        query = query.filter(Asset.warranty_status == warranty_status)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            Asset.asset_code.ilike(search_pattern),
            Asset.brand.ilike(search_pattern),
            Asset.model.ilike(search_pattern),
            Asset.sn.ilike(search_pattern),
            Asset.location.ilike(search_pattern),
        ))

    assets = query.order_by(Asset.asset_code).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "资产台账主索引"

    # 样式定义
    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0052D9", end_color="0052D9", fill_type="solid")
    cell_font = Font(name="微软雅黑", size=10)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )
    red_fill = PatternFill(start_color="FDE8E8", end_color="FDE8E8", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF7E8", end_color="FFF7E8", fill_type="solid")

    headers_list = ["资产编号", "资产分类", "品牌", "型号", "SN号", "位置",
                    "生命周期阶段", "入场日期", "责任人", "维保状态",
                    "维保到期日", "IP地址", "备注"]

    for col, h in enumerate(headers_list, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    today = date.today()
    for row_idx, a in enumerate(assets, 2):
        values = [
            a.asset_code, a.asset_category, a.brand, a.model, a.sn, a.location,
            a.lifecycle_stage, str(a.entry_date) if a.entry_date else "",
            a.responsible_person, a.warranty_status,
            str(a.warranty_expire_date) if a.warranty_expire_date else "",
            a.ip_address, a.remarks or ""
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.font = cell_font
            cell.alignment = center_align
            cell.border = thin_border

        # 维保告警条件格式
        if a.warranty_expire_date and a.lifecycle_stage in ("上架", "运行", "维修"):
            if a.warranty_expire_date < today:
                for col in range(1, len(headers_list) + 1):
                    ws.cell(row=row_idx, column=col).fill = red_fill
            elif a.warranty_expire_date < today + timedelta(days=30):
                ws.cell(row=row_idx, column=11).fill = yellow_fill

    # 设置列宽
    col_widths = [16, 12, 10, 16, 16, 14, 14, 12, 10, 10, 12, 14, 20]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"资产台账导出_{today.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


def export_subtable_excel(db: Session, table_type: str) -> StreamingResponse:
    """导出分表为Excel"""
    table_config = {
        "procurement": (Procurement, "采购入库", [
            ("资产编号", "asset_code"), ("采购单号", "purchase_order"), ("合同号", "contract_no"),
            ("供应商", "supplier"), ("数量", "quantity"), ("单价", "unit_price"),
            ("总价", "total_price"), ("到货日期", "arrival_date"), ("验收人", "inspector"),
            ("验收结果", "inspection_result"), ("上架日期", "install_date"), ("备注", "remarks")
        ]),
        "change": (Change, "变更迁移", [
            ("资产编号", "asset_code"), ("变更类型", "change_type"), ("原位置", "old_location"),
            ("新位置", "new_location"), ("原IP", "old_ip"), ("新IP", "new_ip"),
            ("原责任人", "old_responsible"), ("新责任人", "new_responsible"),
            ("变更原因", "change_reason"), ("审批人", "approver"), ("执行人", "executor"),
            ("执行日期", "execute_date"), ("完成状态", "completion_status"), ("备注", "remarks")
        ]),
        "fault": (Fault, "故障维修", [
            ("资产编号", "asset_code"), ("故障等级", "fault_level"), ("故障现象", "fault_description"),
            ("故障日期", "fault_date"), ("维修人", "repair_person"), ("处理方式", "handle_method"),
            ("配件更换", "parts_replaced"), ("根因分类", "root_cause"), ("恢复日期", "recovery_date"),
            ("停机时长", "downtime_hours"), ("是否复发", "is_recurring"), ("备注", "remarks")
        ]),
        "warranty": (Warranty, "维保续保", [
            ("资产编号", "asset_code"), ("合同编号", "contract_no"), ("覆盖范围", "coverage"),
            ("维保起始日", "start_date"), ("维保到期日", "end_date"), ("续保决策", "renewal_decision"),
            ("决策人", "decision_person"), ("决策日期", "decision_date"),
            ("续保合同号", "renewal_contract_no"), ("续保起始日", "renewal_start_date"),
            ("续保到期日", "renewal_end_date"), ("维保费用", "cost"), ("备注", "remarks")
        ]),
        "retirement": (Retirement, "退役报废", [
            ("资产编号", "asset_code"), ("报废原因", "retire_reason"), ("报废类别", "retire_category"),
            ("申请单号", "application_no"), ("审批人", "approver"), ("审批日期", "approval_date"),
            ("下架日期", "uninstall_date"), ("下架人", "uninstall_person"),
            ("数据清除确认", "data_cleared"), ("数据清除人", "data_clear_person"),
            ("处置方式", "disposal_method"), ("残值回收", "residual_value"), ("备注", "remarks")
        ]),
    }

    if table_type not in table_config:
        raise HTTPException(400, f"不支持的表类型: {table_type}")

    Model, sheet_name, col_defs = table_config[table_type]
    items = db.query(Model).order_by(Model.id.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0052D9", end_color="0052D9", fill_type="solid")
    cell_font = Font(name="微软雅黑", size=10)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

    for col, (header, _) in enumerate(col_defs, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    for row_idx, item in enumerate(items, 2):
        for col, (_, field) in enumerate(col_defs, 1):
            val = getattr(item, field, None)
            if isinstance(val, date):
                val = str(val)
            elif isinstance(val, bool):
                val = "是" if val else "否"
            cell = ws.cell(row=row_idx, column=col, value=val or "")
            cell.font = cell_font
            cell.alignment = center_align
            cell.border = thin_border

            # P1/P2故障标红
            if table_type == "fault" and field == "fault_level" and val in ("P1", "P2"):
                cell.fill = PatternFill(start_color="FDE8E8", end_color="FDE8E8", fill_type="solid")
                cell.font = Font(name="微软雅黑", size=10, bold=True, color="E34D59")

    # 列宽
    for col in range(1, len(col_defs) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 14

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"{sheet_name}导出_{date.today().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


def download_import_template(table_type: str) -> StreamingResponse:
    """下载导入模板（含示例数据和下拉选项提示）"""
    wb = openpyxl.Workbook()
    ws = wb.active

    template_config = {
        "assets": ("资产台账导入模板", [
            ("资产编号*", "资产分类*", "品牌", "型号", "SN号", "位置",
             "生命周期阶段", "入场日期", "责任人", "维保状态", "维保到期日", "IP地址", "备注"),
            [("DC-CL-SRV-001", "服务器", "Dell", "R740", "SN001", "A01-R03-U15",
              "规划", "2026-01-15", "张三", "在保", "2029-01-15", "192.168.1.1", "示例数据")]
        ]),
        "procurement": ("采购入库导入模板", [
            ("资产编号*", "采购单号", "合同号", "供应商", "数量", "单价",
             "总价", "到货日期", "验收人", "验收结果", "上架日期", "备注"),
            [("DC-CL-SRV-001", "PO-2026-001", "CT-2026-001", "戴尔科技", 1, 50000,
             50000, "2026-01-10", "李四", "合格", "2026-01-15", "示例")]
        ]),
        "change": ("变更迁移导入模板", [
            ("资产编号*", "变更类型", "原位置", "新位置", "原IP", "新IP",
             "原责任人", "新责任人", "变更原因", "审批人", "执行人", "执行日期", "完成状态", "备注"),
            [("DC-CL-SRV-001", "位置变更", "A01-R03-U15", "B02-R01-U10",
             "192.168.1.1", "192.168.2.1", "张三", "李四", "机房调整", "运维主管", "王五",
             "2026-06-01", "已完成", "示例")]
        ]),
        "fault": ("故障维修导入模板", [
            ("资产编号*", "故障等级", "故障现象", "故障日期", "维修人", "处理方式",
             "配件更换", "根因分类", "恢复日期", "停机时长", "是否复发", "备注"),
            [("DC-CL-SRV-001", "P3", "端口故障", "2026-06-01", "王五", "现场修复",
             "无", "硬件故障", "2026-06-02", 4, "否", "示例")]
        ]),
        "warranty": ("维保续保导入模板", [
            ("资产编号*", "合同编号", "覆盖范围", "维保起始日", "维保到期日", "续保决策",
             "决策人", "决策日期", "续保合同号", "续保起始日", "续保到期日", "维保费用", "备注"),
            [("DC-CL-SRV-001", "WB-2026-001", "整机维保", "2026-01-15", "2029-01-15", "续保",
             "运维主管", "2026-01-01", "WB-2029-001", "2029-01-15", "2032-01-15", 5000, "示例")]
        ]),
        "retirement": ("退役报废导入模板", [
            ("资产编号*", "报废原因", "报废类别", "申请单号", "审批人", "审批日期",
             "下架日期", "下架人", "数据清除确认", "数据清除人", "处置方式", "残值回收", "备注"),
            [("DC-CL-SRV-001", "设备老化", "正常报废", "RF-2026-001", "运维主管", "2026-06-01",
             "2026-06-05", "王五", "已清除", "安全负责人", "回收商处理", 500, "示例")]
        ]),
    }

    if table_type not in template_config:
        raise HTTPException(400, f"不支持的模板类型: {table_type}")

    sheet_name, (headers, examples) = template_config[table_type]
    ws.title = sheet_name

    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0052D9", end_color="0052D9", fill_type="solid")
    tip_font = Font(name="微软雅黑", size=9, color="8C8E96")
    cell_font = Font(name="微软雅黑", size=10)
    thin_border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
    center_align = Alignment(horizontal="center", vertical="center")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    # 提示行（合法选项说明）
    tip_map_assets = {
        2: "/".join(CATEGORIES),
        7: "/".join(LIFECYCLE_STAGES),
        10: "/".join(WARRANTY_STATUSES),
    }
    tip_map_proc = {10: "/".join(INSPECTION_RESULTS)}
    tip_map_fault = {2: "/".join(FAULT_LEVELS), 6: "/".join(HANDLE_METHODS), 8: "/".join(ROOT_CAUSES)}
    tip_map_warranty = {6: "/".join(RENEWAL_DECISIONS)}
    tip_map_retirement = {3: "/".join(RETIRE_CATEGORIES), 9: "/".join(DATA_CLEAR_OPTIONS)}
    tip_map_change = {2: "/".join(CHANGE_TYPES), 13: "/".join(COMPLETION_STATUSES)}

    all_tip_maps = {
        "assets": tip_map_assets, "procurement": tip_map_proc,
        "fault": tip_map_fault, "warranty": tip_map_warranty,
        "retirement": tip_map_retirement, "change": tip_map_change,
    }
    current_tips = all_tip_maps.get(table_type, {})

    for col, tip in current_tips.items():
        cell = ws.cell(row=2, column=col, value=f"可选: {tip}")
        cell.font = tip_font
        cell.fill = PatternFill(start_color="F3F5F8", end_color="F3F5F8", fill_type="solid")

    # 示例数据行
    for col, val in enumerate(examples[0], 1):
        cell = ws.cell(row=3, column=col, value=val)
        cell.font = cell_font
        cell.alignment = center_align
        cell.border = thin_border
        cell.fill = PatternFill(start_color="E8F0FE", end_color="E8F0FE", fill_type="solid")

    # 空行（供用户填写）
    for row in range(4, 24):
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=row, column=col, value="")
            cell.border = thin_border

    # 列宽
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 16

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"{sheet_name}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


# ============ 报表统计 ============
def get_comprehensive_report(db: Session):
    """综合报表：资产概览+分类分布+阶段分布+维保状态+故障概览"""
    today = date.today()
    total = db.query(Asset).count()

    by_category = dict(db.query(Asset.asset_category, func.count(Asset.id)).group_by(Asset.asset_category).all())
    by_stage = dict(db.query(Asset.lifecycle_stage, func.count(Asset.id)).group_by(Asset.lifecycle_stage).all())
    by_warranty = dict(db.query(Asset.warranty_status, func.count(Asset.id)).group_by(Asset.warranty_status).all())

    # 维保过期/即将过期
    warranty_expired = db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).all()
    warranty_expiring = db.query(Asset).filter(
        Asset.warranty_expire_date.between(today, today + timedelta(days=90)),
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).all()

    # 故障概览
    total_faults = db.query(Fault).count()
    by_fault_level = dict(db.query(Fault.fault_level, func.count(Fault.id)).group_by(Fault.fault_level).all())
    by_root_cause = dict(db.query(Fault.root_cause, func.count(Fault.id)).group_by(Fault.root_cause).all())
    unresolved = db.query(Fault).filter(Fault.recovery_date == None).count()
    avg_downtime = db.query(func.avg(Fault.downtime_hours)).filter(Fault.downtime_hours != None).scalar() or 0

    # 资产年龄分布
    age_buckets = {"0-1年": 0, "1-3年": 0, "3-5年": 0, "5-8年": 0, "8年以上": 0}
    for a in db.query(Asset).filter(Asset.entry_date != None).all():
        if a.entry_date:
            age_days = (today - a.entry_date).days
            age_years = age_days / 365.25
            if age_years < 1: age_buckets["0-1年"] += 1
            elif age_years < 3: age_buckets["1-3年"] += 1
            elif age_years < 5: age_buckets["3-5年"] += 1
            elif age_years < 8: age_buckets["5-8年"] += 1
            else: age_buckets["8年以上"] += 1

    # 变更频率
    by_change_type = dict(db.query(Change.change_type, func.count(Change.id)).group_by(Change.change_type).all())
    total_changes = db.query(Change).count()

    # 采购总额
    total_purchase_cost = db.query(func.sum(Procurement.total_price)).scalar() or 0

    return {
        "total_assets": total,
        "by_category": by_category,
        "by_stage": by_stage,
        "by_warranty": by_warranty,
        "warranty_expired_count": len(warranty_expired),
        "warranty_expired_list": [{"code": a.asset_code, "category": a.asset_category, "expire_date": str(a.warranty_expire_date), "brand": a.brand, "model": a.model} for a in warranty_expired[:20]],
        "warranty_expiring_count": len(warranty_expiring),
        "warranty_expiring_list": [{"code": a.asset_code, "category": a.asset_category, "expire_date": str(a.warranty_expire_date), "days_left": (a.warranty_expire_date - today).days} for a in warranty_expiring[:20]],
        "fault_summary": {
            "total": total_faults,
            "by_level": by_fault_level,
            "by_root_cause": by_root_cause,
            "unresolved": unresolved,
            "avg_downtime_hours": round(avg_downtime, 1)
        },
        "age_distribution": age_buckets,
        "change_summary": {"total": total_changes, "by_type": by_change_type},
        "total_purchase_cost": total_purchase_cost,
    }


def get_warranty_expiry_report(db: Session, days: int = 90):
    """维保到期报表：指定天数内即将到期 + 已过期"""
    today = date.today()
    cutoff = today + timedelta(days=days)

    # 已过期
    expired = db.query(Asset).filter(
        Asset.warranty_expire_date < today,
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).all()

    # 即将到期
    expiring = db.query(Asset).filter(
        Asset.warranty_expire_date.between(today, cutoff),
        Asset.lifecycle_stage.in_(["上架", "运行", "维修"])
    ).all()

    return {
        "expired": [{"asset_code": a.asset_code, "category": a.asset_category, "brand": a.brand, "model": a.model, "location": a.location, "responsible_person": a.responsible_person, "warranty_status": a.warranty_status, "warranty_expire_date": str(a.warranty_expire_date), "days_overdue": (today - a.warranty_expire_date).days} for a in expired],
        "expiring": [{"asset_code": a.asset_code, "category": a.asset_category, "brand": a.brand, "model": a.model, "location": a.location, "responsible_person": a.responsible_person, "warranty_status": a.warranty_status, "warranty_expire_date": str(a.warranty_expire_date), "days_left": (a.warranty_expire_date - today).days} for a in expiring],
        "expired_count": len(expired),
        "expiring_count": len(expiring),
    }


def get_fault_analysis_report(db: Session, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """故障分析报表：故障频率/根因/P级分布/设备故障排行"""
    query = db.query(Fault)
    if start_date:
        query = query.filter(Fault.fault_date >= start_date)
    if end_date:
        query = query.filter(Fault.fault_date <= end_date)

    faults = query.all()

    by_level = {}
    by_root_cause = {}
    by_asset = {}
    by_handle_method = {}
    total_downtime = 0.0
    recurring_count = 0

    for f in faults:
        by_level[f.fault_level] = by_level.get(f.fault_level, 0) + 1
        rc = f.root_cause or "未分类"
        by_root_cause[rc] = by_root_cause.get(rc, 0) + 1
        by_asset[f.asset_code] = by_asset.get(f.asset_code, 0) + 1
        hm = f.handle_method or "未分类"
        by_handle_method[hm] = by_handle_method.get(hm, 0) + 1
        if f.downtime_hours:
            total_downtime += f.downtime_hours
        if f.is_recurring:
            recurring_count += 1

    # 故障设备排行（故障次数前10）
    top_fault_assets = sorted(by_asset.items(), key=lambda x: x[1], reverse=True)[:10]

    # 未恢复故障
    unresolved_by_level = {}
    for f in db.query(Fault).filter(Fault.recovery_date == None).all():
        unresolved_by_level[f.fault_level] = unresolved_by_level.get(f.fault_level, 0) + 1

    return {
        "total_faults": len(faults),
        "by_level": by_level,
        "by_root_cause": by_root_cause,
        "by_handle_method": by_handle_method,
        "total_downtime_hours": round(total_downtime, 1),
        "avg_downtime_hours": round(total_downtime / max(len(faults), 1), 1),
        "recurring_count": recurring_count,
        "top_fault_assets": [{"asset_code": code, "fault_count": count} for code, count in top_fault_assets],
        "unresolved_by_level": unresolved_by_level,
        "unresolved_total": sum(unresolved_by_level.values()),
    }


def get_change_frequency_report(db: Session):
    """变更频率报表"""
    by_type = dict(db.query(Change.change_type, func.count(Change.id)).group_by(Change.change_type).all())
    by_month = {}
    for c in db.query(Change).filter(Change.execute_date != None).all():
        month_key = c.execute_date.strftime("%Y-%m")
        by_month[month_key] = by_month.get(month_key, 0) + 1

    # 按月排序
    by_month = dict(sorted(by_month.items()))

    by_asset = {}
    for c in db.query(Change).all():
        by_asset[c.asset_code] = by_asset.get(c.asset_code, 0) + 1

    top_change_assets = sorted(by_asset.items(), key=lambda x: x[1], reverse=True)[:10]

    total = db.query(Change).count()
    completed = db.query(Change).filter(Change.completion_status == "已完成").count()

    return {
        "total": total,
        "completed": completed,
        "completion_rate": round(completed / max(total, 1) * 100, 1),
        "by_type": by_type,
        "by_month": by_month,
        "top_change_assets": [{"asset_code": code, "change_count": count} for code, count in top_change_assets],
    }
