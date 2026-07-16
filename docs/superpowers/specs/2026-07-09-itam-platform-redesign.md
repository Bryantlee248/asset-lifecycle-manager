# IT Asset Management Platform Redesign Design

## 1. Background

The existing `asset-lifecycle-manager` system is used only as a requirement reference. The new system will not reuse the existing code framework and will not migrate historical data in the MVP phase.

The new product is a multi-tenant, metadata-driven IT asset management platform. It is designed for enterprise internal use with multiple departments and thousands to tens of thousands of assets, while preserving an evolution path toward group-level and stronger tenant isolation scenarios.

## 2. Confirmed Scope

### 2.1 Product Direction

The system is not a simple asset ledger. It is an ITAM platform with lifecycle management as the MVP priority.

The confirmed construction strategy is:

- Use lifecycle MVP first.
- Design the foundation as a platform from day one.
- Start as a modular monolith, not microservices.
- Support multi-tenancy from the first version.
- Treat fields, forms, list views, search conditions, and lightweight permission conditions as metadata.
- Use the old system only as a source of field and process references.

### 2.2 Target Scale

The first version targets:

- Enterprise internal usage.
- Multiple departments and locations.
- Thousands to tens of thousands of assets.
- Future evolution to group-level operation.

### 2.3 Recommended Technology Stack

The recommended stack is:

- Backend: Spring Boot 3.
- Database: PostgreSQL.
- Cache: Redis.
- Frontend: Vue 3 + TypeScript + Vite.
- UI library: Element Plus.
- Database migration: Flyway.
- API documentation: OpenAPI / Swagger.
- Authentication: JWT + refresh token.
- Deployment: Docker Compose first, Kubernetes later.

### 2.4 Tenant Model

The MVP uses shared database and shared tables with `tenant_id` isolation.

The architecture must preserve a future migration path to:

- Shared database with independent schema per tenant.
- Independent database per tenant.

### 2.5 MVP Asset Coverage

Full lifecycle MVP assets:

- Tangible asset: data center assets, including servers, network devices, and security devices.
- Intangible asset: software licenses.

Lightweight MVP assets:

- Certificates and domains: registration, owner, business binding, expiration reminder, renewal record.
- Cloud resources: registration, ownership, cost center, business binding, status management, future cloud-sync interface.

Reserved extension assets:

- Office endpoints.
- Spare parts and consumables.
- SaaS subscriptions.
- More cloud resource types.

## 3. Explicit Non-Goals

The MVP will not:

- Rewrite the existing system in place.
- Migrate existing historical data.
- Build a full low-code platform.
- Build a full BPMN workflow designer.
- Build cloud resource automatic discovery or automatic sync.
- Build a complex CMDB topology graph.
- Build asset auto-scanning.
- Use per-tenant database isolation in the first version.
- Build a full report center.

## 4. MVP Acceptance Boundary

The first usable version is accepted when:

1. A platform administrator can create a tenant.
2. A tenant administrator can configure organizations, users, roles, asset types, fields, forms, and lists.
3. A data center asset can complete purchase, inbound, deployment, operation, change or maintenance, retirement, and disposal.
4. A software license can complete purchase, registration, assignment, renewal, reclaim, and retirement.
5. Different roles, organizations, asset types, and lifecycle states produce different data and field access.
6. Key changes are auditable.
7. Expiration, pending approval, renewal, and retirement tasks can produce reminders.
8. Standard OpenAPI documentation is available.
9. Certificates, domains, and cloud resources can be registered and bound to responsible users and business context.

## 5. Overall Architecture

### 5.1 Architecture Style

The system starts as a modular monolith.

Deployment is a single application in the MVP. Code and domain boundaries are strict enough to allow future extraction into services.

### 5.2 Backend Layering

Backend layering:

```text
api-controller
  -> application-service
    -> domain-service
      -> repository
        -> database
```

Responsibilities:

- Controller handles HTTP, authentication annotations, request validation, and response mapping only.
- Application service orchestrates use cases such as submitting purchase requests or assigning software licenses.
- Domain service contains business rules such as state transitions, permission checks, and metadata validation.
- Repository encapsulates database access.
- Infrastructure provides tenant context, cache, file storage, notification, auditing, and integration adapters.

### 5.3 Core Backend Modules

```text
platform              platform tenant management
identity              users, organizations, roles, authentication
permission            functional, data, field, and state permissions
metadata              asset types, fields, forms, lists, search schemas
asset-core            asset object, attributes, relations
lifecycle             lifecycle templates, states, transitions, events
approval              lightweight approval templates, nodes, instances, tasks
procurement           purchase application and purchase record
inventory             inbound, registration, deployment, reclaim
maintenance           fault, repair, warranty
license               software license, assignment, compliance, renewal
certificate           certificate and domain lightweight management
cloud-resource        cloud resource lightweight registration and sync extension
notification          reminders, in-app notification, email and webhook adapters
audit                 audit logs
attachment            files, contracts, license documents, acceptance sheets
report                MVP dashboards and basic reports
integration           OpenAPI, webhook, external system adapters
common                shared infrastructure and utilities
```

### 5.4 Frontend Architecture

Frontend uses a standard Vue 3 TypeScript project:

```text
src/
  app/
  router/
  layouts/
  modules/
    asset/
    lifecycle/
    license/
    metadata/
    permission/
    approval/
    tenant/
  components/
  api/
  stores/
  utils/
  types/
```

Frontend principles:

- Pages are organized by business module.
- API calls are centrally wrapped.
- Permissions are applied at route, menu, button, and field levels.
- Dynamic forms and dynamic lists are rendered from backend metadata.
- Asset type pages are configuration-driven wherever possible.

### 5.5 Runtime Request Chain

```text
User request
 -> authentication filter
 -> TenantContext resolution
 -> functional permission check
 -> data permission injection
 -> Controller
 -> Application Service
 -> Domain Service
 -> Repository
 -> PostgreSQL
 -> audit log and notification event
 -> response with field permission filtering
```

## 6. Core Domain Model

### 6.1 Asset Core

The `asset` table contains only common fields:

```text
asset
- id
- tenant_id
- asset_no
- asset_name
- asset_kind          tangible / intangible
- asset_type_id
- lifecycle_status
- owner_user_id
- owner_org_id
- location_id
- cost_center_id
- responsible_user_id
- source_type         manual / import / api / discovery
- status              active / inactive / archived
- attributes          jsonb
- created_at
- updated_at
```

`asset_no` is unique within the tenant.

Asset-specific fields are stored in `attributes` unless they are high-frequency query fields or strong relational fields.

### 6.2 Asset Types

```text
asset_type
- id
- tenant_id
- parent_id
- type_code
- type_name
- asset_kind
- lifecycle_template_id
- icon
- enabled
- sort_order
```

Initial type hierarchy:

- Tangible assets
  - Data center assets
    - Server
    - Network device
    - Security device
  - Office endpoints
  - Spare parts and consumables
- Intangible assets
  - Software license
  - Certificate
  - Domain
  - Cloud resource

### 6.3 Dynamic Fields

```text
field_definition
- id
- tenant_id
- asset_type_id
- field_code
- field_name
- field_type
- required
- unique_scope
- default_value
- validation_rule
- data_source
- searchable
- sortable
- visible
- editable
- sensitive
- encrypted
- sort_order
- status
```

MVP field types:

```text
text
textarea
number
decimal
date
datetime
enum
multi_enum
bool
user
org
location
asset_relation
file
url
json
```

Recommended storage is core columns plus JSONB attributes.

Fields that should be physical columns or indexed include:

- `asset_no`
- `asset_name`
- `asset_kind`
- `asset_type_id`
- `lifecycle_status`
- `owner_user_id`
- `owner_org_id`
- `responsible_user_id`
- `location_id`
- `cost_center_id`
- `warranty_end_date`
- `license_end_date`
- `sn`

### 6.4 Asset Relations

```text
asset_relation
- id
- tenant_id
- source_asset_id
- target_asset_id
- relation_type
- description
- created_at
```

Examples:

- Server installed with software license.
- Domain bound to certificate.
- Domain points to cloud resource.
- Cloud resource belongs to business system.
- Device located in rack.

### 6.5 Location

```text
location
- id
- tenant_id
- parent_id
- location_type       campus / building / room / rack / u_position
- location_name
- location_code
```

```text
asset_location_history
- id
- tenant_id
- asset_id
- from_location_id
- to_location_id
- changed_at
- reason
```

## 7. Multi-Tenant and Permission Design

### 7.1 Tenant Isolation

All tenant business tables must contain:

```text
tenant_id
created_by
created_at
updated_by
updated_at
deleted
```

Rules:

- Frontend cannot provide trusted `tenant_id`.
- Backend resolves tenant from token or session.
- All queries inject `tenant_id` automatically.
- All writes fill `tenant_id` automatically.
- Cache keys include tenant prefix.
- Attachment paths include tenant isolation.
- Async tasks carry tenant context.

### 7.2 User Types

Platform users:

- Manage tenants and platform settings.
- Do not participate in tenant asset business by default.
- Need audited managed-access mode to access tenant business data.

Tenant users:

- Belong to a tenant.
- Participate in asset, approval, license, and management workflows.

### 7.3 Permission Layers

The system uses:

```text
Tenant Isolation + RBAC + Data Scope + Field Permission + State Permission
```

Functional permissions control menus, pages, and actions.

Data scope permissions control which business records are visible.

Field permissions control visible and editable fields.

State permissions control which actions are allowed in each lifecycle state.

### 7.4 Suggested Role Templates

Platform:

- `platform_admin`
- `platform_auditor`

Tenant:

- `tenant_admin`
- `asset_admin`
- `asset_operator`
- `license_admin`
- `procurement_user`
- `maintenance_user`
- `department_manager`
- `asset_user`
- `auditor`
- `approver`

### 7.5 Functional Permission Codes

Examples:

```text
asset:view
asset:create
asset:update
asset:delete
asset:import
asset:export
lifecycle:transition
lifecycle:view_history
license:view
license:assign
license:reclaim
license:renew
approval:submit
approval:approve
approval:reject
approval:view
metadata:manage
permission:manage
tenant:user_manage
report:view
audit:view
```

### 7.6 Data Scope Rules

```text
data_scope_rule
- id
- tenant_id
- role_id
- resource_type
- scope_type          self / own_org / own_org_tree / specified_org / specified_location / specified_asset_type / responsible / all_tenant
- scope_value
```

### 7.7 Field Permission Rules

```text
field_permission_rule
- id
- tenant_id
- role_id
- asset_type_id
- field_code
- visible
- editable
- condition_rule
```

Field permissions apply to:

- Detail pages.
- List columns.
- Form fields.
- Export data.
- API responses.

### 7.8 State Permission Rules

```text
state_permission_rule
- id
- tenant_id
- role_id
- asset_type_id
- lifecycle_state
- allowed_actions
```

## 8. Metadata-Driven Design

### 8.1 Metadata Layers

```text
asset_type
field_definition
form_schema
list_view_schema
search_schema
```

### 8.2 Form Schema

```text
form_schema
- id
- tenant_id
- asset_type_id
- form_code
- form_name
- schema_json
- enabled
```

Example:

```json
{
  "sections": [
    {
      "title": "Basic Information",
      "columns": 2,
      "fields": ["asset_no", "asset_name", "brand", "model"]
    },
    {
      "title": "Location",
      "columns": 2,
      "fields": ["location_id", "rack", "u_position"]
    }
  ]
}
```

Runtime form generation combines:

```text
field definitions
+ form layout
+ field permissions
+ state permissions
+ current user data permissions
```

### 8.3 List View Schema

```text
list_view_schema
- id
- tenant_id
- asset_type_id
- view_code
- view_name
- schema_json
- is_default
```

### 8.4 Search Schema

```text
search_schema
- id
- tenant_id
- asset_type_id
- schema_json
```

Supported filter controls:

```text
keyword
enum_select
date_range
user_select
org_tree
location_tree
asset_type_tree
status_select
number_range
```

### 8.5 Metadata Versioning

Recommended model:

```text
metadata_version
- id
- tenant_id
- asset_type_id
- version_no
- status        draft / published / archived
- published_at
```

MVP can implement simple draft and publish behavior.

Deleted fields are disabled, not physically removed, so historical data remains readable.

## 9. Lifecycle and Approval Design

### 9.1 Separation of Concerns

Lifecycle answers:

- What state is the asset in?
- Which actions are possible?

Approval answers:

- Does this action need human approval?
- Who approves?
- What was the approval result?

The MVP uses lifecycle state machine plus lightweight approval templates.

### 9.2 Lifecycle Model

```text
lifecycle_template
- id
- tenant_id
- template_code
- template_name
- asset_kind
- asset_type_id
- enabled
```

```text
lifecycle_state
- id
- tenant_id
- template_id
- state_code
- state_name
- state_category
- sort_order
- is_initial
- is_terminal
```

```text
lifecycle_transition
- id
- tenant_id
- template_id
- from_state
- to_state
- action_code
- action_name
- require_approval
- require_attachment
- guard_rule
```

```text
lifecycle_event
- id
- tenant_id
- asset_id
- from_state
- to_state
- action_code
- operator_id
- reason
- related_process_id
- created_at
```

### 9.3 Data Center Asset Lifecycle

States:

```text
planned
purchasing
inbound
deployed
running
maintenance
retired
disposed
```

Transitions:

```text
planned -> purchasing      submit_purchase
purchasing -> inbound      confirm_inbound
inbound -> deployed        deploy
deployed -> running        start_operation
running -> maintenance     report_fault
maintenance -> running     finish_repair
running -> retired         retire
retired -> disposed        dispose
```

### 9.4 Software License Lifecycle

States:

```text
planned
purchasing
available
assigned
renewal_pending
expired
reclaimed
retired
```

Transitions:

```text
planned -> purchasing          submit_purchase
purchasing -> available        register_license
available -> assigned          assign_license
assigned -> reclaimed          reclaim_license
assigned -> renewal_pending    mark_renewal
renewal_pending -> assigned    renew_license
renewal_pending -> expired     expire
expired -> assigned            renew_after_expired
available -> retired           retire
reclaimed -> available         release_to_pool
```

### 9.5 Approval Model

```text
approval_template
- id
- tenant_id
- template_code
- template_name
- business_type
- enabled
```

```text
approval_node
- id
- tenant_id
- template_id
- node_order
- node_name
- approver_type       role / user / org_manager / asset_owner
- approver_value
- condition_rule
```

```text
approval_instance
- id
- tenant_id
- business_type
- business_id
- status              pending / approved / rejected / cancelled
- applicant_id
- current_node_id
- submitted_at
- completed_at
```

```text
approval_task
- id
- tenant_id
- instance_id
- node_id
- approver_id
- status
- comment
- acted_at
```

MVP approval processes:

- Purchase approval.
- Retirement approval.
- Software license assignment approval.
- Software license renewal approval.

MVP approval modes:

- Single-node approval.
- Sequential multi-node approval.

Not in MVP:

- Countersign.
- Or-sign.
- Add-sign.
- Transfer.
- Complex conditional branches.
- BPMN workflow designer.

## 10. Software License Domain

Software licenses are assets with dedicated domain tables.

```text
software_license
- id
- tenant_id
- asset_id
- license_name
- vendor
- license_model       perpetual / subscription / volume / seat / concurrent
- total_quantity
- used_quantity
- start_date
- end_date
- contract_id
- compliance_status
```

```text
license_assignment
- id
- tenant_id
- license_id
- assigned_to_type    user / org / asset / system
- assigned_to_id
- quantity
- assigned_at
- reclaimed_at
- status
```

Rules:

- Assigned quantity cannot exceed available quantity.
- License assignment can require approval.
- License expiration creates renewal reminders.
- Sensitive fields such as license keys are hidden, masked, or encrypted based on field rules.

## 11. API Design

Base path:

```text
/api/v1
```

Module paths:

```text
/platform
/auth
/tenants
/users
/orgs
/roles
/permissions
/metadata
/assets
/lifecycle
/approvals
/licenses
/certificates
/cloud-resources
/attachments
/notifications
/audit-logs
/reports
/integrations
```

Key rules:

- Business APIs automatically use tenant context.
- Frontend cannot submit trusted `tenant_id`.
- List APIs apply data permissions.
- Detail, list, and export APIs apply field permissions.
- Lifecycle state changes only through action endpoints.
- Write APIs create audit records.

Lifecycle endpoints:

```text
GET  /api/v1/assets/{assetId}/lifecycle
GET  /api/v1/assets/{assetId}/lifecycle/events
GET  /api/v1/assets/{assetId}/lifecycle/actions
POST /api/v1/assets/{assetId}/lifecycle/actions/{actionCode}
```

Approval endpoints:

```text
GET  /api/v1/approvals/tasks/my
GET  /api/v1/approvals/instances
GET  /api/v1/approvals/instances/{id}
POST /api/v1/approvals/instances/{id}/approve
POST /api/v1/approvals/instances/{id}/reject
POST /api/v1/approvals/instances/{id}/cancel
```

License endpoints:

```text
GET  /api/v1/licenses
POST /api/v1/licenses
GET  /api/v1/licenses/{licenseId}
PUT  /api/v1/licenses/{licenseId}
GET  /api/v1/licenses/{licenseId}/assignments
POST /api/v1/licenses/{licenseId}/assignments
POST /api/v1/licenses/{licenseId}/assignments/{assignmentId}/reclaim
POST /api/v1/licenses/{licenseId}/renew
GET  /api/v1/licenses/compliance-summary
```

## 12. MVP Roadmap

### 12.1 MVP-0 Platform Foundation

Goal: build the formal engineering skeleton.

Scope:

- Backend project structure.
- Frontend project structure.
- PostgreSQL and Flyway.
- Tenant foundation.
- Users, organizations, roles.
- JWT login and tenant context.
- Basic RBAC.
- Audit framework.
- OpenAPI documentation.
- Docker Compose local environment.
- Test framework.

Acceptance:

- Platform administrator can create a tenant.
- Tenant administrator can log in.
- Tenant A and tenant B data are isolated.
- API documentation is available.
- Basic audit records exist.

### 12.2 MVP-1 Metadata and Asset Core

Goal: make asset types, fields, forms, lists, and searches configurable.

Scope:

- Asset type tree.
- Field definitions.
- Form schemas.
- List schemas.
- Search schemas.
- Asset object.
- JSONB dynamic fields.
- Asset list, detail, create, edit.
- Initial field permissions.
- Preset metadata for data center assets and software licenses.

### 12.3 MVP-2 Lifecycle Closure

Goal: run the main lifecycle for data center assets and software licenses.

Scope:

- Lifecycle templates.
- Lifecycle states.
- Lifecycle transitions.
- Lifecycle action APIs.
- Lifecycle event logs.
- Data center asset process.
- Software license process.

### 12.4 MVP-3 Approval, Permission, Notification

Goal: control key actions and produce reminders.

Scope:

- Approval templates.
- Approval nodes.
- Approval instances.
- Approval tasks.
- Purchase approval.
- Retirement approval.
- Software license assignment approval.
- Data scope permissions.
- State permissions.
- Enhanced field permissions.
- In-app notifications.
- Expiration reminder jobs.

### 12.5 MVP-4 Import, Export, Reports, Lightweight Assets

Goal: support real operation.

Scope:

- Excel import.
- Excel export.
- Import templates.
- Import validation report.
- Asset overview.
- Lifecycle statistics.
- License usage.
- Expiration reports.
- Pending task reports.
- Certificate and domain lightweight management.
- Cloud resource lightweight management.
- Asset relations.

### 12.6 MVP-5 Production Hardening and Integrations

Goal: prepare for pilot deployment.

Scope:

- Webhook foundation.
- External API tokens.
- Audit query.
- Sensitive field masking.
- Attachment permission.
- Backup strategy.
- System settings.
- Error logs.
- Performance optimization.
- Permission cache.
- Metadata cache.
- CI/CD foundation.

## 13. Engineering Rules

Backend structure:

```text
backend/
  src/main/java/com/company/itam/
    platform/
    identity/
    permission/
    metadata/
    asset/
    lifecycle/
    approval/
    license/
    notification/
    audit/
    attachment/
    report/
    integration/
    common/
  src/main/resources/
    db/migration/
    application.yml
```

Rules:

- All database changes use Flyway.
- All APIs are documented by OpenAPI.
- All business write operations create audit logs.
- All queries pass tenant and permission filters.
- Business logic is not written in controllers.
- Frontend permissions are display-only; backend is authoritative.
- Configuration, field, workflow, and permission changes are traceable.

## 14. Testing Strategy

### 14.1 Unit Tests

Cover:

- Lifecycle state machine.
- Permission decisions.
- Field validation.
- Software license quantity calculation.
- Approval node selection.

### 14.2 Integration Tests

Cover:

- Tenant isolation.
- Data permission filtering.
- Dynamic field save and query.
- Lifecycle action APIs.
- Approval pass and lifecycle transition.

### 14.3 End-to-End Tests

Cover:

- Platform administrator creates tenant.
- Tenant administrator configures asset type.
- Server completes full lifecycle.
- Software license completes assignment, reclaim, renewal.
- Ordinary user sees limited fields.

### 14.4 Security and Permission Tests

Cover:

- Cross-tenant access fails.
- Unauthorized access fails.
- Unauthorized fields are not returned.
- Export does not leak sensitive fields.
- Non-approver cannot operate approval tasks.

## 15. Quality Gates

Each MVP phase must satisfy:

- Backend unit tests pass.
- Backend integration tests pass.
- Frontend build passes.
- API documentation is complete.
- Database migrations are repeatable.
- Tenant isolation tests pass.
- Permission tests pass.
- Critical E2E flows pass.
- Known limitations are documented.

## 16. Pilot Readiness Checklist

Before pilot launch:

- Tenant initialization script.
- Default asset type templates.
- Default field templates.
- Default role and permission templates.
- Default lifecycle templates.
- Default approval templates.
- Deployment documentation.
- Backup and restore plan.
- Audit query.
- Basic monitoring and logging.
- Administrator user guide.
- End user guide.

## 17. Design Conclusion

The recommended system direction is:

```text
Modular Monolith + Multi-Tenant Isolation + Metadata-Driven Assets + Lifecycle-First MVP
```

The first version should validate the model through data center assets and software licenses. Once these two sufficiently different asset categories work through lifecycle, permissions, metadata, approval, audit, and notification, the platform can extend to office assets, spare parts, certificates, domains, cloud resources, contracts, vendors, auto-discovery, and CMDB capabilities without redesigning the foundation.
