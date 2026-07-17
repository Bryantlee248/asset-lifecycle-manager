# Modern Operations Console Design

## Goal

Refresh the IT asset system into a modern operations console while preserving existing APIs, permissions, data fields, tab keys, and business workflows.

## Scope

- Update the visual shell in `frontend/index.html`: fixed navigation, page header, content canvas, typography, spacing, colors, controls, tables, tags, dialogs, drawers, and responsive rules.
- Recompose every existing business tab into a consistent visual hierarchy: page title and summary, filter/action toolbar, main content, and pagination.
- Restyle the approval center sub-tabs, report/configuration sub-tabs, and notification states without changing tab switching logic.
- Replace text/emoji-style navigation treatment with the existing Element Plus icon set where icons are already available.

## Visual System

- Shell: graphite navigation rail, white header, and a restrained light-gray work area.
- Accent colors: blue for primary actions, teal for normal/healthy states, amber for warnings, and red for faults or destructive actions.
- Surfaces: white content panels with 6px radii, subtle borders, and minimal shadow. Avoid gradients and stacked cards.
- Typography: system Chinese sans-serif stack; compact headings and stable 13-14px data-table text.
- Spacing: 8px base scale with consistent 16px section gaps and 24px page padding on desktop.

## Tab Layout Rules

1. Every list tab uses a compact page header, a single filter/action toolbar, then one data surface containing the table and pagination.
2. Dashboard keeps the existing metrics and charts but uses a compact KPI strip and two-column operational overview grid.
3. Approval, reports, and configuration preserve their current sub-tab state but use an underline-style secondary tab bar and clear count/status indicators.
4. Detail dialogs and form drawers group related fields into sections, use two columns on desktop, and keep action buttons in a fixed footer.

## Implementation Boundary

- Modify only `frontend/index.html` for the initial release.
- Reuse Vue state, API calls, Element Plus components, permission checks, and existing event handlers.
- Do not change backend Python files, database schema, endpoints, asset fields, roles, approval behavior, or import/export behavior.

## Acceptance Criteria

- Navigation, dashboard, all list tabs, sub-tabs, dialogs, and drawers share one visual language.
- Existing tab switching and CRUD behavior remain unchanged.
- Main tables are readable at a 1366px desktop viewport without horizontal layout breakage.
- Warning, error, approved, pending, and disabled states remain distinguishable without relying on color alone.
