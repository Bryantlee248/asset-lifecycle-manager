"""
生成100条测试资产数据
覆盖10个分类、7个生命周期阶段，数据拟真度高
"""
import urllib.request
import json
import random
import time

BASE = "http://127.0.0.1:8000"

# ===== 拟真数据池 =====

# 分类 -> (分类码, 品牌列表, 型号列表, 是否有IP)
CATEGORY_MAP = {
    "服务器":   ("SRV", ["Dell", "HP", "联想", "华为", "浪潮", "超聚变"], 
               ["R740xd", "DL380 Gen10", "SR650", "2288H V5", "NF5280M5", "R5300 G5"], True),
    "网络设备": ("NET", ["华为", "思科", "华三", "锐捷", "迈普", "Juniper"],
               ["S5700-48C-EI", "Catalyst 9300", "S5560X-54C-EI", "S2910X-48GT", "NSC-3800", "EX4300"], True),
    "存储设备": ("STG", ["华为", "Dell", "NetApp", "浪潮", "IBM", "Pure Storage"],
               ["OceanStor 5500", "PowerStore 5000", "FAS8700", "AS5600G2", "Storwize V7000", "FlashArray//X20"], True),
    "安全设备": ("SEC", ["深信服", "天融信", "启明星辰", "绿盟", "山石", "华为"],
               ["AF-2000", "NGFW-4000", "天清汉马USG", "NF-3000", "SG-6000", "Secospace USG6000"], True),
    "UPS":      ("UPS", ["APC", "华为", "山特", "伊顿", "维谛", "科士达"],
               ["Smart-UPS SRT 10000", "UPS5000-E-30K", "3C3 Pro 30K", "93PM 30kVA", "Liebert APM 30", "YDC9100S-30"], False),
    "配电设备": ("PWR", ["施耐德", "ABB", "正泰", "西门子", "华为", "维谛"],
               ["Actassi SCS", "Tmax T2N", "NXM-160", "3VA1 160", "FuseLink 100A", "PDU 32A"], False),
    "空调":     ("AC",  ["维谛", "海洛斯", "史图兹", "佳力图", "依米康", "华为"],
               ["Liebert PEX 25kW", "HiRef 30kW", "CSW-30", "MR-30", "ITS-30", "FusionModule500"], False),
    "KVM":      ("KVM", ["Avocent", "Aten", "Raritan", "Tripp Lite", "华为", "Dell"],
               ["AutoView 3108", "CL5708", "Dominion KX III", "B070-008", "eSight KVM", "iDRAC9"], False),
    "PDU":      ("PDU", ["APC", "Raritan", "ServerTech", "施耐德", "华为", "维谛"],
               ["AP7820B", "PX3-5466", "PRO3X 20A", "PM3000", "PDU6300", "MP2-2L1D"], False),
    "其他":     ("OTH", ["Dell", "HP", "联想", "华为", "浪潮", "定制"],
               ["机柜42U", "理线架", "光纤跳线", "网线", "控制台", "配件包"], False),
}

# 生命周期阶段 + 权重（运行阶段占比最高）
STAGES_WEIGHTED = [
    ("规划", 5), ("在途", 8), ("上架", 10), ("运行", 50),
    ("维修", 12), ("待报废", 10), ("已报废", 5),
]

# 机房位置
LOCATIONS = [
    "A栋1楼机房A1", "A栋1楼机房A2", "A栋2楼机房B1", "A栋2楼机房B2",
    "B栋1楼机房C1", "B栋1楼机房C2", "B栋2楼机房D1", "B栋2楼机房D2",
    "C栋1楼核心机房", "C栋2楼网络机房",
]

# 机柜位置
RACKS = [f"{row}{col:02d}" for row in "ABCDEFGH" for col in range(1, 13)]

# 责任人
PERSONS = [
    "张伟", "李强", "王磊", "刘洋", "陈勇", "杨杰", "赵军", "黄涛",
    "周明", "吴鹏", "徐斌", "孙超", "马辉", "朱刚", "胡峰", "林辉",
    "郭亮", "何勇", "高飞", "罗建",
]

# 备注模板
REMARKS_POOL = [
    "设备运行正常", "已纳入年度维保计划", "需定期巡检", "配置变更需审批",
    "关注温度告警", "已安装监控agent", "计划季度更换", "备用设备",
    "关键业务系统", "高可用集群节点", "", "", "", "",  # 部分设备无备注
]

# 维保状态
WARRANTY_STATUSES = {
    "运行": ["在保", "在保", "在保", "即将过期", "已过期"],
    "维修": ["在保", "即将过期", "已过期"],
    "待报废": ["已过期", "即将过期"],
    "已报废": ["已过期"],
    "上架": ["在保", "在保", "即将过期"],
    "在途": ["在保"],
    "规划": ["在保"],
}

# IP段
IP_PREFIXES = ["10.10.1", "10.10.2", "10.10.3", "10.20.1", "10.20.2", "172.16.1", "172.16.2"]


def api(method, path, data=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300]
        return {"error": e.code, "detail": err_body}, e.code


def generate_ip():
    prefix = random.choice(IP_PREFIXES)
    suffix = random.randint(2, 254)
    return f"{prefix}.{suffix}"


def generate_date(year_range):
    year = random.randint(year_range[0], year_range[1])
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def main():
    # 登录
    print("1. 登录系统...")
    r, _ = api("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    token = r.get("token", "")
    if not token:
        print(f"   登录失败: {r}")
        return

    print(f"   登录成功, token: {token[:20]}...")

    # 生成100条资产数据
    print("\n2. 开始生成100条测试资产...")

    success = 0
    fail = 0
    errors = []

    for i in range(1, 101):
        # 选择分类
        category = random.choice(list(CATEGORY_MAP.keys()))
        cat_code, brands, models, has_ip = CATEGORY_MAP[category]

        # 资产编号: DC-CL-[分类码]-[4位序号]
        asset_code = f"DC-CL-{cat_code}-{i:04d}"

        # 品牌+型号
        brand = random.choice(brands)
        model = random.choice(models)

        # SN序列号
        sn = f"SN{random.randint(10000000, 99999999)}"

        # 生命周期阶段
        stages = [s for s, w in STAGES_WEIGHTED for _ in range(w)]
        stage = random.choice(stages)

        # 位置
        location = random.choice(LOCATIONS)
        rack = random.choice(RACKS)
        u_pos = random.randint(1, 42)

        # 责任人 (规划/在途阶段可能无责任人)
        if stage in ("规划", "在途"):
            person = random.choice(PERSONS + [None, None])
        else:
            person = random.choice(PERSONS)

        # 入场日期 (规划/在途阶段可能无入场日期)
        if stage in ("规划", "在途"):
            entry_date = None
        else:
            entry_date = generate_date((2022, 2025))

        # 采购日期 (规划阶段可能无采购日期, 用warranty_expire_date表示采购日期)
        purchase_date = generate_date((2022, 2025))

        # 维保到期日
        if stage == "已报废":
            warranty_expire = None
        elif stage == "待报废":
            warranty_expire = generate_date((2024, 2025))
        elif stage in ("维修", "运行"):
            warranty_expire = random.choice([
                generate_date((2025, 2026)),
                generate_date((2026, 2027)),
                generate_date((2024, 2025)),  # 部分已过期
            ])
        else:
            warranty_expire = generate_date((2026, 2028))

        # 维保状态
        warranty_statuses = WARRANTY_STATUSES.get(stage, ["在保"])
        warranty_status = random.choice(warranty_statuses)

        # IP地址 (服务器/网络设备/存储/安全设备有IP)
        ip_address = generate_ip() if has_ip and stage in ("上架", "运行", "维修") else None

        # 备注
        remarks = random.choice(REMARKS_POOL)

        # 资产名称
        asset_name = f"{category}-{brand}-{model}-{i:03d}"

        asset_data = {
            "asset_code": asset_code,
            "asset_category": category,
            "brand": brand,
            "model": model,
            "sn": sn,
            "location": f"{location} {rack}U{u_pos}" if stage not in ("规划", "在途") else location,
            "lifecycle_stage": stage,
            "entry_date": entry_date,
            "responsible_person": person,
            "warranty_status": warranty_status,
            "warranty_expire_date": warranty_expire,
            "ip_address": ip_address,
            "remarks": remarks,
        }

        r, status = api("POST", "/api/assets", asset_data, token=token)
        if status == 200:
            success += 1
            if i % 20 == 0:
                print(f"   已生成 {i}/100 条...")
        else:
            fail += 1
            errors.append(f"#{i} {asset_code}: {r}")
            if fail <= 5:
                print(f"   失败 #{i}: {asset_code} -> {r}")

    print(f"\n3. 生成完成!")
    print(f"   成功: {success} 条")
    print(f"   失败: {fail} 条")
    if errors:
        print(f"   错误详情(前5条):")
        for e in errors[:5]:
            print(f"     {e}")

    # 验证统计
    print("\n4. 验证数据统计...")
    r, _ = api("GET", "/api/assets", token=token)
    total = r.get("total", 0) if isinstance(r, dict) else len(r) if isinstance(r, list) else 0
    print(f"   数据库资产总数: {total}")

    # 按分类统计
    items = r.get("items", r) if isinstance(r, dict) else r
    if isinstance(items, list):
        from collections import Counter
        by_cat = Counter(a.get("asset_category", "") for a in items)
        by_stage = Counter(a.get("lifecycle_stage", "") for a in items)
        print(f"   按分类:")
        for cat, count in sorted(by_cat.items()):
            print(f"     {cat}: {count} 台")
        print(f"   按阶段:")
        for stage_name in ["规划", "在途", "上架", "运行", "维修", "待报废", "已报废"]:
            count = by_stage.get(stage_name, 0)
            print(f"     {stage_name}: {count} 台")


if __name__ == "__main__":
    main()
