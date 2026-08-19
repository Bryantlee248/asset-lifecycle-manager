"""P0 实机冒烟：API + DB 直查"""
import json, urllib.request, urllib.error, sqlite3, sys

BASE = "http://127.0.0.1:8000"
DB = r"D:\workbuddy\运维体系重塑方案\asset-lifecycle-manager\asset_lifecycle.db"

def post(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(), headers=headers, method="POST")
    return _do(req)

def get(path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, headers=headers, method="GET")
    return _do(req)

def _do(req):
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception as e:
        return None, str(e)

def login(user, pwd):
    st, body = post("/api/auth/login", {"username": user, "password": pwd})
    if st == 200 and "token" in body:
        return body["token"]
    return None

results = []
def chk(name, cond, extra=""):
    results.append((name, "PASS" if cond else "FAIL", extra))
    print(("PASS " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))

# 1) 登录 admin
admin = login("admin", "Admin@2026!Secure")
chk("admin 登录", admin is not None)
if not admin:
    print(json.dumps(results, ensure_ascii=False)); sys.exit(1)

# 2) 下拉结构零变更：19 字段 + 关键值集合
st, dd = get("/api/config/dropdowns", admin)
expected_fields = ["categories","lifecycle_stages","warranty_statuses","inspection_results","change_types",
"fault_levels","handle_methods","root_causes","renewal_decisions","retire_categories","data_clear_options",
"completion_statuses","receive_types","outbound_categories","procurement_approval_statuses","warranty_types",
"disposal_methods","ownership_types","inbound_inspection_results"]
chk("dropdowns 200", st == 200, str(st))
chk("dropdowns 19 字段齐全", set(expected_fields) <= set(dd.keys()), f"缺:{set(expected_fields)-set(dd.keys())}")
chk("fault_levels 值正确", dd.get("fault_levels") == ["P1","P2-严重","P3","P4"], str(dd.get("fault_levels")))
chk("inspection_results(3值)", dd.get("inspection_results") == ["合格","不合格","待验收"], str(dd.get("inspection_results")))
chk("inbound_inspection_results(2值)", dd.get("inbound_inspection_results") == ["合格","不合格"], str(dd.get("inbound_inspection_results")))
chk("categories 含配电设备/PDU", "配电设备" in dd.get("categories",[]) and "PDU" in dd.get("categories",[]), str(dd.get("categories")))

# 3) 分组树
st, groups = get("/api/config/dictionary-groups", admin)
chk("dictionary-groups 200", st == 200, str(st))
chk("分组数=17", isinstance(groups, list) and len(groups) == 17, f"len={len(groups) if isinstance(groups,list) else 'NA'}")

# 4) 枚举项列表
st, dicts = get("/api/config/dictionaries?group_code=fault_level", admin)
chk("dictionaries 200", st == 200, str(st))
chk("fault_level 枚举=4", isinstance(dicts, list) and len(dicts) == 4, f"len={len(dicts) if isinstance(dicts,list) else 'NA'}")

# 5) 分类列表
st, cats = get("/api/config/categories", admin)
chk("categories 列表 200", st == 200, str(st))
chk("分类数=10", isinstance(cats, list) and len(cats) == 10, f"len={len(cats) if isinstance(cats,list) else 'NA'}")

# 6) 引用保护
st, ref = get("/api/config/references?kind=fault_level&value=P1", admin)
chk("references 200", st == 200, str(st))
chk("references 结构", isinstance(ref, dict) and "count" in ref, str(ref))

# 7) RBAC：viewer 调配置写/读接口应 403
viewer = login("test_viewer", "Test@2026!")
chk("viewer 登录", viewer is not None)
if viewer:
    st, _ = get("/api/config/dictionary-groups", viewer)
    chk("viewer 配置接口 403", st == 403, f"st={st}")
    st, _ = get("/api/config/dropdowns", viewer)
    chk("viewer 下拉接口 200(全员可读)", st == 200, f"st={st}")

# 8) DB 直查：seed 计数 + 存量零 orphan
con = sqlite3.connect(DB)
cur = con.cursor()
g = cur.execute("SELECT COUNT(*) FROM dictionary_groups").fetchone()[0]
d = cur.execute("SELECT COUNT(*) FROM dictionaries").fetchone()[0]
c = cur.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
chk("DB groups=17", g == 17, f"g={g}")
chk("DB dictionaries=63", d == 63, f"d={d}")
chk("DB categories=10", c == 10, f"c={c}")
# 零 orphan：assets.asset_category 全部命中 categories.category_name
orphan = cur.execute(
    "SELECT DISTINCT asset_category FROM assets WHERE asset_category IS NOT NULL AND asset_category != '' "
    "AND asset_category NOT IN (SELECT category_name FROM categories)").fetchall()
chk("存量资产分类零 orphan", len(orphan) == 0, f"orphan={[r[0] for r in orphan]}")
# 零 orphan：asset_inbound.asset_category
orphan2 = cur.execute(
    "SELECT DISTINCT asset_category FROM asset_inbound WHERE asset_category IS NOT NULL AND asset_category != '' "
    "AND asset_category NOT IN (SELECT category_name FROM categories)").fetchall()
chk("移入表分类零 orphan", len(orphan2) == 0, f"orphan={[r[0] for r in orphan2]}")
con.close()

print("\n==== 汇总 ====")
fails = [r for r in results if r[1] == "FAIL"]
for n, s, e in results:
    print(f"  [{s}] {n}" + (f"  ({e})" if e else ""))
print(f"\n总计 {len(results)} 项，失败 {len(fails)} 项")
sys.exit(1 if fails else 0)
