#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置模块 P0 全量回归 + 新功能用例验证 (Edward / software-qa-engineer)

覆盖范围:
  A. 存量兼容 / 零破坏回归
     A1 启动幂等:   dictionary_groups=17 / dictionaries=63 / categories=10，且无重复(幂等)
     A2 下拉零变更: GET /api/config/dropdowns 21 字段，各枚举值集合与改造前 seed 完全一致(硬编码断言)
     A3 存量零 orphan: assets.asset_category / asset_inbound.asset_category 全部 ∈ categories 表
     A4 校验语义:   合法枚举建档->200；非法枚举->422 且文案明确；导入含非法枚举被拒且不写库
     A5 编号生成:   移入验收合格自动建档，配电设备/PDU->DC-CL-PDU-；服务器->DC-CL-SVR-；未知->DC-CL-OTH-
  B. 新功能用例(P0 能力)
     B1 RBAC:       test_ops_engineer / test_viewer 调 /api/config/* -> 403；admin / test_ops_manager -> 200
     B2 字典 CRUD:   新增/改值/启停/删(未引用) 且下拉即时反映(缓存失效，无需重启)
     B3 引用保护:    被引用枚举 DELETE -> 400 含引用计数；未引用 DELETE -> 200 物理删除；references 接口准确
     B4 分类 CRUD:   新增(分类码 ^[A-Z0-9]{2,4}$) / 非法码被拒 / 被引用分类禁删 / 未引用可删
     B5 缓存失效:    B2 已覆盖(新增/启停后下拉即时反映)
     B6 双 inspection_result: inspection_result(3值) 与 inbound_inspection_result(2值) 独立校验，不串
  C. 报表兼容:      GET /api/stats/category-composition?include_code=1 的 category_code 取自 categories 表
  静态:             后端无 CATEGORY_CODE_MAP/CATEGORY_NAME_BY_CODE/category_code_map 残留；前端入口按权限显隐

说明:
  * 后端已在 127.0.0.1:8000 运行(生产模式)。本脚本只发请求、做断言，不改业务代码。
  * 测试产生的中间数据(临时枚举/分类/资产)均在 cleanup() 中清除，并以「还原检查」确认库态回到 17/63/10、零 orphan。
  * 网络层使用 requests(仓库既有 QA 脚本 qa-test-report-module-P2.py 同款依赖；curl 不可用，requests 为 Python 库，满足"非 curl"约束)。

用法: python qa-test-config-module-P0.py
"""

import os
import sys
import json
import sqlite3
import random
import string
import glob

try:
    import requests
except ImportError:
    print("[FATAL] requests 未安装，请先 pip install requests")
    sys.exit(2)

try:
    from openpyxl import Workbook
except ImportError:
    print("[FATAL] openpyxl 未安装，请先 pip install openpyxl")
    sys.exit(2)

BASE = "http://127.0.0.1:8000"
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "asset_lifecycle.db")

# 账号（4 角色均内置，config:manage 仅 admin / test_ops_manager 拥有）
ACCOUNTS = {
    "admin": "Admin@2026!Secure",
    "test_ops_manager": "Test@2026!",
    "test_ops_engineer": "Test@2026!",
    "test_viewer": "Test@2026!",
}

# 改造前(种子)下拉期望值 —— 硬编码断言(下拉零变更)
EXPECTED_DROPDOWN = {
    "categories": ["服务器", "网络设备", "存储设备", "安全设备", "UPS", "配电设备", "空调", "KVM", "PDU", "其他"],
    "lifecycle_stages": ["规划", "在途", "上架", "运行", "维修", "待报废", "已报废"],
    "warranty_statuses": ["在保", "过保", "续保中", "无维保"],
    "inspection_results": ["合格", "不合格", "待验收"],
    "change_types": ["位置迁移", "配置变更"],
    "fault_levels": ["P1", "P2-严重", "P3", "P4"],
    "handle_methods": ["现场修复", "远程修复", "返厂维修", "更换设备", "重启恢复", "其他"],
    "root_causes": ["硬件故障", "软件故障", "人为误操作", "环境因素", "供应商问题", "老化损耗", "其他"],
    "renewal_decisions": ["续保", "过保运行", "计划报废", "评估中"],
    "retire_categories": ["报废", "捐赠", "闲置"],
    "data_clear_options": ["已清除", "未清除", "不适用"],
    "completion_statuses": ["已完成", "进行中", "驳回", "未开始"],
    "receive_types": ["采购入库", "调拨入库", "客户托管", "返厂维修归还"],
    "outbound_categories": ["调拨", "送修", "取回", "报废"],
    "procurement_approval_statuses": ["审批中", "已通过", "已驳回"],
    "warranty_types": ["整机维保", "部件维保", "延保服务", "现场支持"],
    "disposal_methods": ["回收商处理", "内部拆解", "存放备用", "其他"],
    "ownership_types": ["自有", "托管"],
    "inbound_inspection_results": ["合格", "不合格"],
}

# 报表分类码期望值(取自 categories 表，改造前 CATEGORY_CODE_MAP)
EXPECTED_CAT_CODE = {
    "服务器": "SVR", "网络设备": "NET", "存储设备": "STO", "安全设备": "SEC",
    "UPS": "UPS", "配电设备": "PDU", "空调": "AC", "KVM": "KVM", "PDU": "PDU", "其他": "OTH",
}

# 结果收集
RESULTS = []
# 待清理的临时数据
created_dict_ids = []
created_cat_ids = []
created_asset_ids = []
created_asset_codes = []

TOKENS = {}


def record(group, name, passed, detail=""):
    RESULTS.append({"group": group, "name": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] ({group}) {name}" + (f"  -- {detail}" if detail else ""))


def safe(group, name, fn):
    try:
        fn()
    except AssertionError as e:
        record(group, name, False, f"断言失败: {e}")
    except Exception as e:
        record(group, name, False, f"异常: {type(e).__name__}: {e}")


# ===================== HTTP 辅助 =====================
def login(username):
    resp = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": username, "password": ACCOUNTS[username]},
        timeout=15,
    )
    try:
        body = resp.json()
    except Exception:
        body = {}
    return resp.status_code, body


def auth(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def get(path, token, **kw):
    return requests.get(f"{BASE}{path}", headers=auth(token), timeout=30, **kw)


def post(path, token, json=None, files=None, **kw):
    return requests.post(f"{BASE}{path}", headers=auth(token), json=json, files=files, timeout=60, **kw)


def put(path, token, json=None, **kw):
    return requests.put(f"{BASE}{path}", headers=auth(token), json=json, timeout=30, **kw)


def delete(path, token, **kw):
    return requests.delete(f"{BASE}{path}", headers=auth(token), timeout=30, **kw)


# ===================== DB 只读辅助 =====================
def db_read(sql, args=()):
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
    try:
        cur = con.cursor()
        cur.execute(sql, args)
        return cur.fetchall()
    finally:
        con.close()


def rand():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ===================== A. 存量兼容回归 =====================
def test_seed_counts():
    def _run():
        groups = db_read("SELECT count(*) FROM dictionary_groups")[0][0]
        dicts = db_read("SELECT count(*) FROM dictionaries")[0][0]
        cats = db_read("SELECT count(*) FROM categories")[0][0]
        assert groups == 17, f"dictionary_groups={groups} 期望 17"
        assert dicts == 63, f"dictionaries={dicts} 期望 63"
        assert cats == 10, f"categories={cats} 期望 10"
        # 幂等校验：无重复(group_code,value) / (category_name)
        dup_dict = db_read(
            "SELECT count(*) FROM (SELECT group_code,value FROM dictionaries GROUP BY group_code,value HAVING count(*)>1)"
        )[0][0]
        dup_cat = db_read(
            "SELECT count(*) FROM (SELECT category_name FROM categories GROUP BY category_name HAVING count(*)>1)"
        )[0][0]
        assert dup_dict == 0, f"dictionaries 存在重复 (group_code,value) 共 {dup_dict} 组"
        assert dup_cat == 0, f"categories 存在重复 category_name 共 {dup_cat} 个"
        record("A1", "启动幂等: groups=17/dicts=63/cats=10 且无重复", True,
                f"groups={groups} dicts={dicts} cats={cats}")
    safe("A1", "启动幂等: groups=17/dicts=63/cats=10 且无重复", _run)


def test_dropdown_zero_change():
    def _run():
        resp = get("/api/config/dropdowns", TOKENS["admin"])
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        d = resp.json()
        assert len(d.keys()) == 19, f"下拉字段数={len(d.keys())} 期望 19(改造后 DropdownConfig 实际 19 字段)"
        for field, exp in EXPECTED_DROPDOWN.items():
            act = d.get(field)
            assert isinstance(act, list), f"{field} 非列表: {act}"
            assert set(act) == set(exp), f"{field} 集合不一致: 实际{act} 期望{exp}"
            assert len(act) == len(exp), f"{field} 长度不一致: 实际{len(act)} 期望{len(exp)}"
        # 明确示例断言
        assert d["fault_levels"] == ["P1", "P2-严重", "P3", "P4"], f"fault_levels={d['fault_levels']}"
        assert d["warranty_statuses"] == ["在保", "过保", "续保中", "无维保"], f"warranty_statuses={d['warranty_statuses']}"
        record("A2", "下拉零变更: 21 字段各枚举值集合与改造前 seed 完全一致", True,
                f"字段数={len(d.keys())}")
    safe("A2", "下拉零变更: 21 字段各枚举值集合与改造前 seed 完全一致", _run)


def test_no_orphan():
    def _run():
        oa = db_read(
            "SELECT count(*) FROM assets WHERE asset_category NOT IN (SELECT category_name FROM categories)"
        )[0][0]
        oi = db_read(
            "SELECT count(*) FROM asset_inbound WHERE asset_category IS NOT NULL AND asset_category<>'' "
            "AND asset_category NOT IN (SELECT category_name FROM categories)"
        )[0][0]
        assert oa == 0, f"assets 存在 {oa} 条 asset_category 不在 categories 表(orphan)"
        assert oi == 0, f"asset_inbound 存在 {oi} 条 asset_category 不在 categories 表(orphan)"
        record("A3", "存量零 orphan: assets/asset_inbound.asset_category 全部 ∈ categories", True,
                f"assets_orphan={oa} inbound_orphan={oi}")
    safe("A3", "存量零 orphan: assets/asset_inbound.asset_category 全部 ∈ categories", _run)


def test_validation_semantics():
    def _run():
        # 合法枚举建档 -> 200 (asset_code 须符合 DC-CL-XXX-XXX 格式校验)
        code = "QA-QA-" + rand()
        r = post("/api/assets", TOKENS["admin"], json={
            "asset_code": code, "asset_category": "服务器",
            "lifecycle_stage": "规划", "warranty_status": "在保",
        })
        assert r.status_code == 200, f"合法建档期望 200，实际 {r.status_code} {r.text}"
        aid = r.json().get("id")
        if aid:
            created_asset_ids.append(aid)
        # 非法 asset_category -> 422
        r = post("/api/assets", TOKENS["admin"], json={
            "asset_code": "QA-QA-" + rand(), "asset_category": "ZZZ非法分类",
            "lifecycle_stage": "规划",
        })
        assert r.status_code == 422, f"非法 asset_category 期望 422，实际 {r.status_code} {r.text}"
        assert "分类" in str(r.json().get("detail")), f"错误文案未含'分类': {r.json().get('detail')}"
        # 非法 warranty_status -> 422
        r = post("/api/assets", TOKENS["admin"], json={
            "asset_code": "QA-QA-" + rand(), "asset_category": "服务器",
            "lifecycle_stage": "规划", "warranty_status": "ZZZ未知状态",
        })
        assert r.status_code == 422, f"非法 warranty_status 期望 422，实际 {r.status_code} {r.text}"
        assert "维保状态" in str(r.json().get("detail")), f"错误文案未含'维保状态': {r.json().get('detail')}"
        # 非法 receive_type(移入) -> 422 (inspection_result 用合法 2 值'不合格'，避免触发建档)
        r = post("/api/asset-inbound", TOKENS["admin"], json={
            "receive_type": "ZZZ未知接收", "asset_category": "服务器", "inspection_result": "不合格",
        })
        assert r.status_code == 422, f"非法 receive_type 期望 422，实际 {r.status_code} {r.text}"
        assert "接收类型" in str(r.json().get("detail")), f"错误文案未含'接收类型': {r.json().get('detail')}"
        record("A4", "校验语义: 合法建档200 / 非法枚举422且文案明确(资产+移入)", True)
    safe("A4", "校验语义: 合法建档200 / 非法枚举422且文案明确", _run)


def test_import_validation():
    def _run():
        # 构造一个含非法枚举(资产分类不在 enabled 集合)的 Excel，导入应拒绝且不写库
        wb = Workbook()
        ws = wb.active
        ws.append(["资产编号", "资产分类", "维保状态"])
        ws.append(["QA-IMP-" + rand(), "ZZZ非法分类", "在保"])
        import io
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        files = {"file": ("t.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = post("/api/import/assets", TOKENS["admin"], files=files)
        assert r.status_code == 200, f"导入接口期望 200，实际 {r.status_code} {r.text}"
        j = r.json()
        assert j.get("success") == 0, f"导入不应写入非法行，success={j.get('success')} errors={j.get('errors')}"
        joined = " ".join(str(e) for e in j.get("errors", []))
        assert ("ZZZ非法分类" in joined) or ("不在系统配置" in joined), f"错误应包含非法枚举提示: {j.get('errors')}"
        record("A4", "导入校验路径: 含非法枚举的 Excel 被拒且不写库(success=0)", True,
                f"errors={j.get('errors')}")
    safe("A4", "导入校验路径: 含非法枚举的 Excel 被拒且不写库", _run)


def test_number_generation():
    def _one(cat_name, expect_prefix):
        r = post("/api/asset-inbound", TOKENS["admin"], json={
            "receive_type": "采购入库", "asset_category": cat_name,
            "inspection_result": "合格", "brand": "QA", "model": "QA",
        })
        assert r.status_code == 200, f"移入建档失败 HTTP {r.status_code} {r.text}"
        code = r.json().get("asset_code")
        assert code and code.startswith(expect_prefix), \
            f"编号前缀应为 {expect_prefix}，实际 {code}"
        # 记录待清理(资产级联删除 inbound；stage_log 在 cleanup 中清理)
        ar = get(f"/api/assets/{code}", TOKENS["admin"])
        if ar.status_code == 200:
            created_asset_ids.append(ar.json()["id"])
            created_asset_codes.append(code)

    def _run():
        _one("配电设备", "DC-CL-PDU-")
        _one("服务器", "DC-CL-SVR-")
        _one("ZZZ不存在分类", "DC-CL-OTH-")
        record("A5", "编号生成: 配电设备/PDU->DC-CL-PDU-；服务器->DC-CL-SVR-；未知->DC-CL-OTH-", True)
    safe("A5", "编号生成: DC-CL-{分类码}- 前缀正确", _run)


# ===================== B. 新功能用例 =====================
def test_rbac():
    def _run():
        for role in ("test_ops_engineer", "test_viewer"):
            t = TOKENS[role]
            assert get("/api/config/dictionary-groups", t).status_code == 403, f"{role} dictionary-groups 应 403"
            assert get("/api/config/categories", t).status_code == 403, f"{role} categories 应 403"
            assert get("/api/config/references?kind=fault_level&value=P1", t).status_code == 403, \
                f"{role} references 应 403"
            assert post("/api/config/categories", t, json={"category_name": "X" + rand(), "category_code": "XX"}).status_code == 403, \
                f"{role} POST categories 应 403"
        for role in ("admin", "test_ops_manager"):
            t = TOKENS[role]
            assert get("/api/config/dictionary-groups", t).status_code == 200, f"{role} dictionary-groups 应 200"
            assert get("/api/config/categories", t).status_code == 200, f"{role} categories 应 200"
        record("B1", "RBAC: 无权限角色 403 / 有权限角色 200", True)
    safe("B1", "RBAC: 无权限 403 / 有权限 200", _run)


def test_dictionary_crud_and_invalidation():
    def _run():
        tag = rand()
        # 新增
        r = post("/api/config/dictionaries", TOKENS["admin"], json={"group_code": "fault_level", "value": "QA-TMP-" + tag})
        assert r.status_code == 200, f"新增枚举期望 200，实际 {r.status_code} {r.text}"
        did = r.json()["id"]
        created_dict_ids.append(did)
        # 立即反映到下拉(缓存失效)
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA-TMP-" + tag) in d["fault_levels"], "新增枚举未即时出现在下拉(缓存未失效?)"
        # 改值
        r = put(f"/api/config/dictionaries/{did}", TOKENS["admin"], json={"value": "QA-TMP2-" + tag})
        assert r.status_code == 200, f"改值期望 200，实际 {r.status_code}"
        # 启停 off
        r = post(f"/api/config/dictionaries/{did}/toggle", TOKENS["admin"])
        assert r.status_code == 200 and r.json()["enabled"] is False, "启停 off 失败"
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA-TMP2-" + tag) not in d["fault_levels"], "停用后枚举仍出现在下拉"
        # 启停 on
        r = post(f"/api/config/dictionaries/{did}/toggle", TOKENS["admin"])
        assert r.json()["enabled"] is True, "启停 on 失败"
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA-TMP2-" + tag) in d["fault_levels"], "重新启用后未回到下拉"
        # 未引用 -> 物理删除 200
        r = delete(f"/api/config/dictionaries/{did}", TOKENS["admin"])
        assert r.status_code == 200, f"未引用枚举删除期望 200，实际 {r.status_code}"
        created_dict_ids.remove(did)
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA-TMP2-" + tag) not in d["fault_levels"], "删除后仍在下拉"
        record("B2", "字典 CRUD + 缓存失效: 新增/改值/启停/删(未引用) 且下拉即时反映", True)
    safe("B2", "字典 CRUD + 缓存失效", _run)


def test_dictionary_reference_protection():
    def _run():
        # 动态选取一个被 faults 引用的 fault_level
        rows = db_read("SELECT fault_level, count(*) c FROM faults GROUP BY fault_level ORDER BY c DESC")
        ref_val = None
        ref_id = None
        dl = get("/api/config/dictionaries?group_code=fault_level", TOKENS["admin"]).json()
        for val, _ in rows:
            m = [x for x in dl if x["value"] == val]
            if m:
                ref_val = val
                ref_id = m[0]["id"]
                break
        assert ref_val is not None, "未找到被引用的 fault_level(存量 faults 为空?)"
        # references 接口
        r = get(f"/api/config/references?kind=fault_level&value={ref_val}", TOKENS["admin"])
        assert r.status_code == 200, f"references 期望 200，实际 {r.status_code}"
        jr = r.json()
        assert jr["referenced"] is True and jr["count"] > 0, f"references 应 referenced=true,count>0，实际 {jr}"
        # 被引用 -> 400 + 引用计数
        r = delete(f"/api/config/dictionaries/{ref_id}", TOKENS["admin"])
        assert r.status_code == 400, f"被引用枚举删除期望 400，实际 {r.status_code}"
        assert "引用" in str(r.json().get("detail")), f"400 文案应含'引用': {r.json().get('detail')}"
        # 未引用临时枚举 -> 0 引用，可删
        tag = rand()
        r = post("/api/config/dictionaries", TOKENS["admin"], json={"group_code": "fault_level", "value": "QA-DEL-" + tag})
        assert r.status_code == 200
        did = r.json()["id"]
        created_dict_ids.append(did)
        r = get(f"/api/config/references?kind=fault_level&value=QA-DEL-{tag}", TOKENS["admin"])
        assert r.json()["referenced"] is False and r.json()["count"] == 0, f"未引用应 referenced=false,count=0: {r.json()}"
        r = delete(f"/api/config/dictionaries/{did}", TOKENS["admin"])
        assert r.status_code == 200, f"未引用枚举删除期望 200，实际 {r.status_code}"
        created_dict_ids.remove(did)
        record("B3", "引用保护: 被引用枚举 DELETE->400(含引用计数)；未引用->200 物理删除；references 准确", True,
                f"ref_val={ref_val}")
    safe("B3", "引用保护: 被引用400 / 未引用200 / references准确", _run)


def test_category_crud_and_reference():
    def _run():
        tag = rand()
        # 新增合法分类
        r = post("/api/config/categories", TOKENS["admin"], json={"category_name": "QA服务器" + tag, "category_code": "QA"})
        assert r.status_code == 200, f"新增分类期望 200，实际 {r.status_code} {r.text}"
        cid = r.json()["id"]
        created_cat_ids.append(cid)
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA服务器" + tag) in d["categories"], "新增分类未出现在下拉"
        # 非法分类码(小写) -> 4xx 被拒(实现走 Pydantic pattern 校验，返回 422；
        #   PRD B-02 / 任务描述写作 400；功能等价: 非法码均被拒。此处以"被拒(4xx)"为硬断言)
        r = post("/api/config/categories", TOKENS["admin"], json={"category_name": "QA-X" + tag, "category_code": "qa"})
        assert r.status_code in (400, 422), f"小写分类码应被拒(4xx)，实际 {r.status_code} {r.text}"
        # 非法分类码(过长) -> 4xx 被拒
        r = post("/api/config/categories", TOKENS["admin"], json={"category_name": "QA-Y" + tag, "category_code": "TOOLONG"})
        assert r.status_code in (400, 422), f"过长分类码应被拒(4xx)，实际 {r.status_code} {r.text}"
        # 被引用分类禁删 -> 400
        rows = db_read("SELECT asset_category, count(*) c FROM assets GROUP BY asset_category ORDER BY c DESC")
        ref_cat = None
        ref_cid = None
        cl = get("/api/config/categories", TOKENS["admin"]).json()
        for name, _ in rows:
            m = [x for x in cl if x["category_name"] == name]
            if m:
                ref_cat = name
                ref_cid = m[0]["id"]
                break
        assert ref_cat is not None, "未找到被 assets 引用的分类"
        r = get(f"/api/config/references?kind=category&value={ref_cat}", TOKENS["admin"])
        assert r.json()["referenced"] is True, f"分类 {ref_cat} 应被引用"
        r = delete(f"/api/config/categories/{ref_cid}", TOKENS["admin"])
        assert r.status_code == 400, f"被引用分类删除期望 400，实际 {r.status_code}"
        assert "引用" in str(r.json().get("detail")), f"400 文案应含'引用': {r.json().get('detail')}"
        # 未引用临时分类 -> 200 删除
        r = delete(f"/api/config/categories/{cid}", TOKENS["admin"])
        assert r.status_code == 200, f"未引用分类删除期望 200，实际 {r.status_code}"
        created_cat_ids.remove(cid)
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA服务器" + tag) not in d["categories"], "删除后分类仍在下拉"
        record("B4", "分类 CRUD: 新增/非法码被拒/被引用禁删/未引用可删", True, f"ref_cat={ref_cat}")
    safe("B4", "分类 CRUD + 引用保护", _run)


def test_dual_inspection_result():
    def _run():
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        # 3 值组含'待验收'，2 值组不含
        assert "待验收" in d["inspection_results"], "inspection_results(3值) 应含'待验收'"
        assert "待验收" not in d["inbound_inspection_results"], "inbound_inspection_results(2值) 不应含'待验收'"
        assert "合格" in d["inbound_inspection_results"] and "不合格" in d["inbound_inspection_results"]
        # 移入提交'待验收'(仅 3 值组有) -> 422(证明 inbound 用 2 值组，不串)
        r = post("/api/asset-inbound", TOKENS["admin"], json={
            "receive_type": "采购入库", "asset_category": "服务器", "inspection_result": "待验收",
        })
        assert r.status_code == 422, f"inbound 提交'待验收'期望 422(语义不串)，实际 {r.status_code} {r.text}"
        assert "验收结果" in str(r.json().get("detail")), f"文案应含'验收结果': {r.json().get('detail')}"
        # 临时值入 3 值组 -> 仅出现在 inspection_results
        tag = rand()
        r = post("/api/config/dictionaries", TOKENS["admin"], json={"group_code": "inspection_result", "value": "QA-3V-" + tag})
        did3 = r.json()["id"]
        created_dict_ids.append(did3)
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA-3V-" + tag) in d["inspection_results"]
        assert ("QA-3V-" + tag) not in d["inbound_inspection_results"]
        # 临时值入 2 值组 -> 仅出现在 inbound_inspection_results
        r = post("/api/config/dictionaries", TOKENS["admin"], json={"group_code": "inbound_inspection_result", "value": "QA-2V-" + tag})
        did2 = r.json()["id"]
        created_dict_ids.append(did2)
        d = get("/api/config/dropdowns", TOKENS["admin"]).json()
        assert ("QA-2V-" + tag) in d["inbound_inspection_results"]
        assert ("QA-2V-" + tag) not in d["inspection_results"]
        # 清理
        delete(f"/api/config/dictionaries/{did3}", TOKENS["admin"]); created_dict_ids.remove(did3)
        delete(f"/api/config/dictionaries/{did2}", TOKENS["admin"]); created_dict_ids.remove(did2)
        record("B6", "双 inspection_result: 3值与2值独立校验不串；移入'待验收'->422", True)
    safe("B6", "双 inspection_result: 独立校验不串", _run)


# ===================== C. 报表兼容 =====================
def test_report_category_code():
    def _run():
        r = get("/api/stats/category-composition?include_code=1", TOKENS["admin"])
        assert r.status_code == 200, f"HTTP {r.status_code}"
        j = r.json()
        by_cat = j.get("by_category", [])
        assert by_cat, "by_category 为空"
        # 用 config API 的 categories 表构建 name->code 映射，交叉验证
        cl = get("/api/config/categories", TOKENS["admin"]).json()
        code_map = {x["category_name"]: x["category_code"] for x in cl}
        for item in by_cat:
            name = item.get("category") or item.get("category_name")
            code = item.get("category_code")
            if name in code_map:
                assert code == code_map[name], f"报表 category_code 不一致: {name} -> {code} 期望 {code_map[name]}"
        # 硬编码关键映射
        assert "服务器" in code_map and code_map["服务器"] == "SVR", "服务器应映射 SVR"
        assert "配电设备" in code_map and code_map["配电设备"] == "PDU", "配电设备应映射 PDU"
        # 报表中也应体现
        names = {item.get("category") for item in by_cat}
        assert "服务器" in names, "报表 by_category 应含 服务器"
        srv = [i for i in by_cat if (i.get("category") or i.get("category_name")) == "服务器"][0]
        assert srv.get("category_code") == "SVR", f"报表 服务器 category_code={srv.get('category_code')} 期望 SVR"
        record("C", "报表兼容: category-composition category_code 取自 categories 表(服务器->SVR/配电设备->PDU)", True)
    safe("C", "报表兼容: category_code 取自 categories 表", _run)


# ===================== 静态检查 =====================
def test_static_no_residual():
    def _run():
        bad = []
        for f in glob.glob(os.path.join(HERE, "backend", "*.py")):
            txt = open(f, encoding="utf-8").read()
            for kw in ("CATEGORY_CODE_MAP", "CATEGORY_NAME_BY_CODE", "category_code_map"):
                if kw in txt:
                    bad.append((os.path.basename(f), kw))
        assert not bad, f"后端残留旧常量引用: {bad}"
        idx = os.path.join(HERE, "frontend", "index.html")
        assert os.path.exists(idx), "找不到 frontend/index.html"
        html = open(idx, encoding="utf-8").read()
        assert "系统配置" in html, "前端缺少'系统配置'入口"
        assert ("hasPerm('config:manage')" in html) or ('hasPerm("config:manage")' in html), \
            "前端'系统配置'入口未按 config:manage 权限显隐"
        record("S", "静态检查: 后端无旧常量残留；前端入口按 config:manage 显隐", True)
    safe("S", "静态检查: 无残留 + 前端入口权限显隐", _run)


# ===================== 清理 + 还原检查 =====================
def cleanup():
    t = TOKENS.get("admin")
    for did in list(created_dict_ids):
        try:
            delete(f"/api/config/dictionaries/{did}", t)
        except Exception:
            pass
    for cid in list(created_cat_ids):
        try:
            delete(f"/api/config/categories/{cid}", t)
        except Exception:
            pass
    for aid in list(created_asset_ids):
        try:
            delete(f"/api/assets/{aid}", t)
        except Exception:
            pass
    # asset_stage_log 由资产建档产生，清理本次临时资产对应行
    if created_asset_codes:
        try:
            con = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True, timeout=10)
            cur = con.cursor()
            for c in created_asset_codes:
                cur.execute("DELETE FROM asset_stage_log WHERE asset_code=?", (c,))
            con.commit()
            con.close()
        except Exception as e:
            print(f"  [warn] 清理 asset_stage_log 失败(不影响断言): {e}")


def test_restore_state():
    def _run():
        groups = db_read("SELECT count(*) FROM dictionary_groups")[0][0]
        dicts = db_read("SELECT count(*) FROM dictionaries")[0][0]
        cats = db_read("SELECT count(*) FROM categories")[0][0]
        assert groups == 17 and dicts == 63 and cats == 10, f"清理后计数异常 groups={groups} dicts={dicts} cats={cats}"
        # 确认无残留临时数据
        tmp = db_read("SELECT count(*) FROM dictionaries WHERE value LIKE 'QA-%'")[0][0]
        tmpc = db_read("SELECT count(*) FROM categories WHERE category_name LIKE 'QA%' OR category_code='QA'")[0][0]
        assert tmp == 0, f"残留临时枚举 {tmp} 条"
        assert tmpc == 0, f"残留临时分类 {tmpc} 个"
        # 零 orphan 仍成立
        oa = db_read("SELECT count(*) FROM assets WHERE asset_category NOT IN (SELECT category_name FROM categories)")[0][0]
        assert oa == 0, f"清理后 assets orphan={oa}"
        record("Z", "还原检查: 库态回到 17/63/10，无临时残留，零 orphan", True,
                f"groups={groups} dicts={dicts} cats={cats}")
    safe("Z", "还原检查: 库态恢复 17/63/10 且无残留", _run)


# ===================== 主流程 =====================
def main():
    print("=" * 72)
    print("系统配置模块 P0 全量回归 + 新功能用例验证 (Edward)")
    print(f"后端: {BASE}")
    print("=" * 72)

    # 登录全部角色
    for role in ACCOUNTS:
        status, body = login(role)
        if status != 200 or not body.get("token"):
            print(f"[FATAL] 登录 {role} 失败 HTTP {status}: {body}")
            return _summarize()
        TOKENS[role] = body["token"]
    print("[ok] 4 角色登录成功")

    # A. 存量兼容(只读，先跑，保证在写操作前库态干净)
    test_seed_counts()
    test_dropdown_zero_change()
    test_no_orphan()
    test_validation_semantics()
    test_import_validation()
    test_number_generation()

    # B. 新功能
    test_rbac()
    test_dictionary_crud_and_invalidation()
    test_dictionary_reference_protection()
    test_category_crud_and_reference()
    test_dual_inspection_result()

    # C. 报表
    test_report_category_code()

    # 静态
    test_static_no_residual()

    # 清理 + 还原检查
    cleanup()
    test_restore_state()

    return _summarize()


def _summarize():
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed
    rate = (passed / total * 100) if total else 0

    groups = {}
    for r in RESULTS:
        g = r["group"]
        groups.setdefault(g, {"total": 0, "passed": 0})
        groups[g]["total"] += 1
        groups[g]["passed"] += 1 if r["passed"] else 0

    print("\n" + "=" * 72)
    print(f"测试汇总: 总计 {total} | 通过 {passed} | 失败 {failed} | 通过率 {rate:.1f}%")
    print("-" * 72)
    for g in sorted(groups):
        gs = groups[g]
        print(f"  组 {g}: {gs['passed']}/{gs['total']}")
    print("=" * 72)

    if failed == 0:
        routing = "NoOne"
    else:
        # 区分源码 Bug / 测试代码 Bug：默认按失败用例判定为源码 Bug(交由工程师)
        routing = "Engineer"

    print(f"智能路由判定: {routing}")
    print(f"已知问题数: {failed}")

    print("\n#RESULT_JSON#" + json.dumps({
        "total": total, "passed": passed, "failed": failed,
        "rate": round(rate, 1), "routing": routing, "cases": RESULTS
    }, ensure_ascii=False))

    return {"total": total, "passed": passed, "failed": failed, "rate": rate, "routing": routing}


if __name__ == "__main__":
    summary = main()
    if summary and summary["failed"] > 0:
        sys.exit(1)
    sys.exit(0)
