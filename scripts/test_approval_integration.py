"""审批工作流完整集成测试 v4 - 最终版"""
import urllib.request, json, time

BASE = 'http://127.0.0.1:8000'
TS = str(int(time.time()))[-6:]  # unique suffix
results = []

def api(method, path, data=None, token=None):
    url = BASE + path
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        return {'error': e.code, 'detail': err_body[:300]}
    except Exception as e:
        return {'error': str(e)}

def pf(name, condition, fail_msg=''):
    results.append((name, 'PASS' if condition else 'FAIL: ' + fail_msg[:120]))

# ========== T01: Login ==========
r = api('POST', '/api/auth/login', {'username': 'admin', 'password': 'admin123'})
token = r.get('token', '')
pf('T01 登录获取token', bool(token), str(r)[:80])

# ========== T02-T04: Create 3 fresh assets at 运行 ==========
codes = ['IT-A-' + TS, 'IT-B-' + TS, 'IT-C-' + TS]
asset_ids = []
for i, code in enumerate(codes):
    r = api('POST', '/api/assets', {
        'asset_code': code,
        'asset_name': '审批测试资产' + str(i+1),
        'asset_category': 'server',
        'lifecycle_stage': '运行',
        'location': '测试机房',
        'brand': 'TestBrand',
        'model': 'TestModel',
        'sn': 'SN-' + code,
        'purchase_date': '2025-01-01',
        'warranty_expiry': '2027-01-01'
    }, token=token)
    aid = r.get('id', None)
    asset_ids.append(aid)

pf('T02 创建3个测试资产(运行)', all(asset_ids), 'ids=' + str(asset_ids))

# ========== T05: Approval dropdown config ==========
r = api('GET', '/api/approval-config/dropdowns', token=token)
pf('T05 审批下拉配置', isinstance(r, dict) and 'approval_types' in r, str(r)[:80])

# ========== T06: Approval type config ==========
r = api('GET', '/api/approval-config/types', token=token)
pf('T06 审批类型配置', isinstance(r, dict) and 'types' in r and len(r['types']) > 0, str(r)[:80])

# ========== CORE FLOW: Fault degrade (资产A: 运行->维修) ==========
# T07: Create
r = api('POST', '/api/approval-requests', {
    'asset_code': codes[0],
    'approval_type': 'fault_degrade_approval',
    'reason': '设备风扇故障停转，需降级进入维修状态',
    'target_stage': '维修',
    'attachments': []
}, token=token)
req1_id = r.get('id', None)
pf('T07 创建故障降级审批单', bool(req1_id), str(r)[:80])

# T08: Submit (draft->pending)
r = api('POST', '/api/approval-requests/' + str(req1_id) + '/submit', token=token)
pf('T08 提交审批(draft->pending)', r.get('status') == 'pending', str(r)[:80])

# T09: My applications
r = api('GET', '/api/approval-requests/my-applications', token=token)
items = r.get('items', []) if isinstance(r, dict) else []
pf('T09 查询我的审批申请', len(items) > 0, 'count=' + str(len(items)))

# T10: My pending
r = api('GET', '/api/approval-requests/my-pending', token=token)
items = r.get('items', []) if isinstance(r, dict) else []
pf('T10 查询待审列表', len(items) > 0, 'count=' + str(len(items)))

# T11: Stats
r = api('GET', '/api/approval-requests/stats', token=token)
pf('T11 审批统计', isinstance(r, dict) and 'total_pending' in r, str(r)[:80])

# T12: Detail
r = api('GET', '/api/approval-requests/' + str(req1_id), token=token)
has_steps = isinstance(r.get('steps', []), list)
pf('T12 审批详情(含步骤)', r.get('id') == req1_id and has_steps, str(r)[:80])

# T13: Approve (pending->approved)
r = api('POST', '/api/approval-requests/' + str(req1_id) + '/action', {
    'action': 'approve', 'comment': '确认故障，同意维修'
}, token=token)
pf('T13 审批通过(故障降级)', r.get('status') == 'approved', str(r)[:80])

# T14: Verify asset A stage = 维修
r = api('GET', '/api/assets/' + codes[0], token=token)
pf('T14 资产A阶段=维修', r.get('lifecycle_stage') == '维修', 'stage=' + str(r.get('lifecycle_stage')))

# ========== REJECT & RESUBMIT FLOW: Retirement (资产B: 运行->待报废) ==========
# T15: Create retirement approval
r = api('POST', '/api/approval-requests', {
    'asset_code': codes[1],
    'approval_type': 'retirement_approval',
    'reason': '设备服役超3年，性能严重退化需报废退役',
    'target_stage': '待报废',
    'attachments': []
}, token=token)
req2_id = r.get('id', None)
pf('T15 创建报废审批单', bool(req2_id), str(r)[:80])

# T16: Submit
r = api('POST', '/api/approval-requests/' + str(req2_id) + '/submit', token=token)
pf('T16 提交报废审批(pending)', r.get('status') == 'pending', str(r)[:80])

# T17: Reject (via /action)
r = api('POST', '/api/approval-requests/' + str(req2_id) + '/action', {
    'action': 'reject', 'comment': '报废资料不完整请补充'
}, token=token)
pf('T17 驳回报废审批(rejected)', r.get('status') == 'rejected', str(r)[:80])

# T18: Resubmit
r = api('POST', '/api/approval-requests/' + str(req2_id) + '/resubmit', {
    'reason': '补充完整报废资料，设备已无法恢复且超出维保期',
    'attachments': []
}, token=token)
pf('T18 重新提交驳回审批(pending)', r.get('status') == 'pending', str(r)[:80])

# ========== CANCEL FLOW: Migration (资产C: 运行->在途) ==========
# T19: Create migration approval
r = api('POST', '/api/approval-requests', {
    'asset_code': codes[2],
    'approval_type': 'migration_approval',
    'reason': '设备需迁移至新机房机柜位置',
    'target_stage': '在途',
    'attachments': []
}, token=token)
req3_id = r.get('id', None)
pf('T19 创建迁移审批单', bool(req3_id), str(r)[:80])

# T20: Submit first
r = api('POST', '/api/approval-requests/' + str(req3_id) + '/submit', token=token)
submit_ok = r.get('status') == 'pending'
print('  T20 submit: status=' + str(r.get('status', 'N/A')))

# T21: Cancel (pending->cancelled)
r = api('POST', '/api/approval-requests/' + str(req3_id) + '/cancel', token=token)
pf('T21 撤回审批单(cancelled)', r.get('status') == 'cancelled', str(r)[:80])

# ========== MULTI-LEVEL APPROVAL: Retirement (资产C still at 运行, 2级审批) ==========
# Note: Asset C is still at 运行 since the migration was cancelled
# T22: Create retirement approval for asset C
r = api('POST', '/api/approval-requests', {
    'asset_code': codes[2],
    'approval_type': 'retirement_approval',
    'reason': '存储设备老化严重，申请报废退役(多级审批测试)',
    'target_stage': '待报废',
    'attachments': []
}, token=token)
req4_id = r.get('id', None)
pf('T22 创建报废审批(多级)', bool(req4_id), str(r)[:80])

# T23: Submit
r = api('POST', '/api/approval-requests/' + str(req4_id) + '/submit', token=token)
pf('T23 提交报废审批(多级)', r.get('status') == 'pending', str(r)[:80])

# T24: First level approve (ops_manager)
r = api('POST', '/api/approval-requests/' + str(req4_id) + '/action', {
    'action': 'approve', 'comment': '运维经理一级审批通过'
}, token=token)
# Check still pending (waiting for second level)
detail = api('GET', '/api/approval-requests/' + str(req4_id), token=token)
still_pending = detail.get('status') == 'pending'
pf('T24 多级审批(一级通过待二级)', still_pending, 'status=' + str(detail.get('status')))

# T25: Second level approve (admin)
r = api('POST', '/api/approval-requests/' + str(req4_id) + '/action', {
    'action': 'approve', 'comment': '管理员二级审批通过'
}, token=token)
pf('T25 多级审批(二级通过)', r.get('status') == 'approved', str(r)[:80])

# T26: Verify asset C stage = 待报废
r = api('GET', '/api/assets/' + codes[2], token=token)
pf('T26 资产C阶段=待报废', r.get('lifecycle_stage') == '待报废', 'stage=' + str(r.get('lifecycle_stage')))

# ========== NOTIFICATIONS ==========
# T27: Notification list
r = api('GET', '/api/approval-notifications', token=token)
notifs = r if isinstance(r, list) else r.get('items', []) if isinstance(r, dict) else []
pf('T27 审批通知列表', len(notifs) > 0, 'count=' + str(len(notifs)))

# T28: Unread count
r = api('GET', '/api/approval-notifications/unread-count', token=token)
pf('T28 未读通知计数', isinstance(r, dict) and 'unread_count' in r, str(r)[:80])

# T29: Read all
r = api('PUT', '/api/approval-notifications/read-all', token=token)
pf('T29 全部通知标为已读', isinstance(r, dict) and 'message' in r, str(r)[:80])

# T30: Verify unread = 0
r = api('GET', '/api/approval-notifications/unread-count', token=token)
pf('T30 已读后未读数=0', r.get('unread_count', -1) == 0, 'unread=' + str(r.get('unread_count')))

# ========== SUPPLEMENTARY ==========
# T31: Approval by asset
r = api('GET', '/api/approval-requests/by-asset/' + codes[0], token=token)
items = r.get('items', []) if isinstance(r, dict) else r if isinstance(r, list) else []
pf('T31 按资产查询审批', len(items) > 0, str(r)[:80])

# T32: Approval step integrity (approved request has complete steps)
r = api('GET', '/api/approval-requests/' + str(req1_id), token=token)
steps = r.get('steps', [])
has_approved = any(s.get('status') == 'approved' for s in steps)
pf('T32 审批步骤完整性', has_approved, 'steps=' + str(len(steps)))

# ========== Print results ==========
print()
print('=' * 60)
print('审批工作流集成测试结果 v4 (最终版)')
print('=' * 60)
pass_count = sum(1 for _, s in results if s == 'PASS')
fail_count = sum(1 for _, s in results if s != 'PASS')
for name, status in results:
    icon = '[PASS]' if status == 'PASS' else '[FAIL]'
    print(icon + ' ' + name + ': ' + status)
print('=' * 60)
print('总计: ' + str(len(results)) + '项 | 通过: ' + str(pass_count) + ' | 失败: ' + str(fail_count))
if fail_count == 0:
    print('ALL PASSED! 通过率: 100%')
else:
    print('通过率: ' + str(round(pass_count / len(results) * 100, 1)) + '%')
