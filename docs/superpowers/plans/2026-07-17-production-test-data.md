# Production Test Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely add 100 identifiable test assets and six test users to the production system through its authenticated HTTP API.

**Architecture:** Use an authenticated browser origin or a user-supplied temporary administrator credential to issue HTTP API requests. The credential obtains an in-memory token only; no database path, credential, or token is written to disk. Read state before every write; create only the missing test records and make no delete or update request except disabling the newly created `test_disabled` account.

**Tech Stack:** Existing browser administrator session or in-memory API token, FastAPI endpoints `/api/auth/login`, `/api/config/dropdowns`, `/api/assets`, `/api/roles`, and `/api/users`.

---

## File Structure

- Create: `docs/superpowers/specs/2026-07-17-production-test-data-design.md` - approved data boundary.
- Create: `docs/superpowers/plans/2026-07-17-production-test-data.md` - operational execution record.
- No application source files are changed.

### Task 1: Read production state without mutation

**Files:**

- Modify: none

- [ ] **Step 1: Read the available categories, roles, assets, and users from the browser origin**

Run the following JavaScript in the authenticated application page:

```javascript
const request = async (path) => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
};

const [dropdowns, roles, assets, users] = await Promise.all([
  request('/api/config/dropdowns'),
  request('/api/roles'),
  request('/api/assets?page=1&page_size=100&search=DC-CL-TST-'),
  request('/api/users?page=1&page_size=100&search=test_'),
]);

const requiredRoleCodes = ['admin', 'ops_manager', 'ops_engineer', 'viewer'];
const roleByCode = new Map(roles.items.map((role) => [role.code, role]));
const missingRoles = requiredRoleCodes.filter((code) => !roleByCode.has(code));
const category = dropdowns.categories?.[0];
if (!category || missingRoles.length) {
  throw new Error(`preflight failed: category=${category}, missingRoles=${missingRoles.join(',')}`);
}
```

Expected: the browser returns an enabled asset category and the four required role codes. No POST, PUT, or DELETE request is made.

- [ ] **Step 2: Confirm the test identifiers are absent or safely reusable**

Run:

```javascript
const testAssets = assets.items.filter((item) => item.asset_code.startsWith('DC-CL-TST-'));
const testUsers = users.items.filter((item) => item.username.startsWith('test_'));
({ testAssetCodes: testAssets.map((item) => item.asset_code), testUsers: testUsers.map((item) => item.username) });
```

Expected: only the prescribed `DC-CL-TST-001` to `DC-CL-TST-100` and six `test_` user names may be reused. Any conflicting identifier stops execution and is reported.

### Task 2: Create the missing test assets and users

**Files:**

- Modify: none

- [ ] **Step 1: Write the browser-side preflight assertion**

Run this assertion before the write loop:

```javascript
const expectedAssetCodes = Array.from({ length: 100 }, (_, index) =>
  `DC-CL-TST-${String(index + 1).padStart(3, '0')}`,
);
const expectedUserRoles = new Map([
  ['test_admin', 'admin'],
  ['test_ops_manager', 'ops_manager'],
  ['test_ops_engineer_1', 'ops_engineer'],
  ['test_ops_engineer_2', 'ops_engineer'],
  ['test_viewer', 'viewer'],
  ['test_disabled', 'viewer'],
]);
const knownAssetCodes = new Set(assets.items.map((item) => item.asset_code));
const knownUsernames = new Set(users.items.map((item) => item.username));
const unexpectedAssets = testAssets.filter((item) => !expectedAssetCodes.includes(item.asset_code));
const unexpectedUsers = testUsers.filter((item) => !expectedUserRoles.has(item.username));
if (unexpectedAssets.length || unexpectedUsers.length) {
  throw new Error('preflight failed: unexpected existing test identifiers');
}
```

Expected: the assertion passes only when all existing test records match the approved identifier set.

- [ ] **Step 2: Create only the missing assets through `/api/assets`**

Run:

```javascript
const post = async (path, body) => {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(`${path}: ${JSON.stringify(payload)}`);
  return payload;
};

const createdAssets = [];
const skippedAssets = [];
for (let index = 1; index <= 100; index += 1) {
  const assetCode = `DC-CL-TST-${String(index).padStart(3, '0')}`;
  if (knownAssetCodes.has(assetCode)) {
    skippedAssets.push(assetCode);
    continue;
  }
  await post('/api/assets', {
    asset_code: assetCode,
    asset_category: category,
    brand: 'TestLab',
    model: `Test-Model-${String(index).padStart(3, '0')}`,
    sn: `TESTSN20260717${String(index).padStart(3, '0')}`,
    lifecycle_stage: '规划',
    room: 'TEST-ROOM',
    cabinet: 'TEST-RACK',
    u_position: `U${index}`,
    device_name: `测试资产-${String(index).padStart(3, '0')}`,
    department: '测试数据',
    remarks: '测试数据：可安全删除的演示资产',
  });
  createdAssets.push(assetCode);
}
```

Expected: `createdAssets.length + skippedAssets.length === 100`; any failed request stops the loop and records its API response.

- [ ] **Step 3: Create only the missing users and disable the designated account**

Run:

```javascript
const createdUsers = [];
const skippedUsers = [];
const userByName = new Map(users.items.map((item) => [item.username, item]));
for (const [username, roleCode] of expectedUserRoles) {
  if (knownUsernames.has(username)) {
    skippedUsers.push(username);
    continue;
  }
  const user = await post('/api/users', {
    username,
    password: 'TempTest#2026',
    real_name: `测试用户 ${username}`,
    department: '测试数据',
    role_ids: [roleByCode.get(roleCode).id],
  });
  userByName.set(username, user);
  createdUsers.push(username);
}

const disabledUser = userByName.get('test_disabled');
if (disabledUser?.status !== 'disabled') {
  const response = await fetch(`/api/users/${disabledUser.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'disabled' }),
  });
  if (!response.ok) throw new Error(`/api/users/${disabledUser.id}: HTTP ${response.status}`);
}
```

Expected: all six user names exist; only `test_disabled` has status `disabled`.

### Task 3: Verify and report the production result

**Files:**

- Modify: none

- [ ] **Step 1: Re-read the created data**

Run:

```javascript
const [verifiedAssets, verifiedUsers] = await Promise.all([
  request('/api/assets?page=1&page_size=100&search=DC-CL-TST-'),
  request('/api/users?page=1&page_size=100&search=test_'),
]);
const verifiedAssetCodes = new Set(verifiedAssets.items.map((item) => item.asset_code));
const verifiedUserByName = new Map(verifiedUsers.items.map((item) => [item.username, item]));
const missingAssets = expectedAssetCodes.filter((code) => !verifiedAssetCodes.has(code));
const missingUsers = [...expectedUserRoles.keys()].filter((name) => !verifiedUserByName.has(name));
if (missingAssets.length || missingUsers.length || verifiedUserByName.get('test_disabled')?.status !== 'disabled') {
  throw new Error(`verification failed: assets=${missingAssets.join(',')}; users=${missingUsers.join(',')}`);
}
({ createdAssets, skippedAssets, createdUsers, skippedUsers, verifiedTestAssets: expectedAssetCodes.length });
```

Expected: no missing asset or user; `test_disabled` is disabled. Report the created and skipped identifiers without printing an authentication token.

- [ ] **Step 2: Record the outcome in the handoff**

Report the public health response, number of created and skipped test assets, number of created and skipped test users, the common temporary password, and any preflight or API failure. Do not report browser session storage or bearer token values.
