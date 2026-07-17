# Production Test Data Design

## Goal

Add a safe, identifiable test dataset to the deployed IT asset system for demonstration and functional checks.

## Scope

- Ensure exactly 100 test assets exist with codes `DC-CL-TST-001` through `DC-CL-TST-100`.
- Create six test users: `test_admin`, `test_ops_manager`, `test_ops_engineer_1`, `test_ops_engineer_2`, `test_viewer`, and `test_disabled`.
- Use the existing browser administrator session or an explicitly supplied temporary administrator credential, and application APIs only.

## Data Rules

- Every test asset has a Chinese remark containing `测试数据` and a test-specific device name.
- Existing non-test assets and users are never changed or deleted.
- Existing objects with the prescribed test code or username are skipped, making a repeat run idempotent.
- Roles are resolved from the production role list by code. If a required role is missing, that user is reported as skipped rather than creating or changing roles.
- `test_disabled` is created as a viewer and then disabled.
- All created test users use the temporary password `TempTest#2026`.

## Execution and Validation

1. Read the existing assets, users, roles, and enabled asset categories through the authenticated API.
2. Create only missing test assets and users in small batches.
3. Re-read the API and verify the 100 prescribed asset codes, the six test usernames, assigned roles, and the disabled status.
4. Report created, skipped, and failed records without exposing the administrator session token.

## Exclusions

- No direct database access.
- A supplied temporary credential is used only to obtain an in-memory API token; neither credential nor token is written to disk, Git, or the handoff.
- No deletion, reset, or modification of non-test records.
- No deployment or source-code change.
