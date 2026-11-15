# LabAdda Google-Grade Central & Hierarchical Calendar Specification & Ledger

**Status**: In Progress  
**Initial Date**: 2026-11-15  
**Time Zone**: Indian Standard Time (`Asia/Kolkata`, UTC+5:30)  
**Deployment Target**: Air-gapped Intranet LabAdda Instance  

---

## 1. Executive Summary & Objectives

The goal of this work package is to build and integrate a modern, central, Google Calendar-like scheduling and event management system into LabAdda. Research teams, laboratories, divisions, sections, and individual staff members require clear visibility into schedules across the organization without cluttering or leaking confidential projects.

Key objectives:
1. **Multi-Level Hierarchy Event Visibility**:
   - **Site-Wide Events**: High-level institute notices, holidays, all-hands seminars visible to all active users. Managed by Site Administrators and root stewards.
   - **Hierarchical Unit Events**: Events created at Division, Group, or Section levels. Following LabAdda's upward-only hierarchy grant model:
     - A Section member sees their Section's events, plus events of their parent Division, parent Group, and Root.
     - A Division member does *not* see child Section events unless they are explicitly assigned to that Section.
   - **Projects and Collaborative Groups**: Flat, private calendars strictly restricted to members of those specific workspaces.
   - **Personal Calendars**: Isolated, user-owned personal calendar for individual tasks, meetings, and deadlines. Completely blind to administrators and other users.
2. **Modern Google-Like Experience**:
   - Month, Week, Day, and Agenda/Schedule views.
   - Color-coded event chips mapped by calendar source.
   - Left sidebar with quick "Create Event" button, mini calendar navigator, and toggleable calendar source filters.
   - Indian Standard Time (IST) formatting for all date/time pickers and displays.
3. **Air-Gap and Zero Regression Guarantee**:
   - Zero external CDN or internet dependency.
   - 100% backward compatibility with existing noticeboard, whiteboard, chat, tasks, and notes features.
   - Lossless database migrations with upgrade and downgrade checks.

---

## 2. Security, Privacy & Authorization Rules

In strict adherence to `AGENTS.md`:
1. **Admin Blindness**:
   - Site administrators do **not** gain access to personal calendars or private project calendars simply by virtue of being administrators.
   - Personal events (`owner_id = user_id`) are accessible only by the owning user. Requests by any other user (including admin) return uniform `404 Not Found`.
2. **Hierarchy Rule (Upward-Only)**:
   - For workspace events, access is verified against `policy.readable_workspace_ids(db, user)`.
   - If User A belongs to `Section S` under `Division D`, `readable_workspace_ids` contains both `S` and `D`. User A sees events in `S` and `D`.
   - If User B belongs only to `Division D`, `readable_workspace_ids` contains `D` but not `S`. User B never sees events in `Section S`.
3. **Write Permissions**:
   - **Personal**: Owned by user; user can create, update, delete.
   - **Workspace**: Users with `can_write` (members in open workspaces, or stewards) can create events. The creator, workspace stewards, or moderators can update/delete.
   - **Site-Wide**: Only Site Administrators and root unit stewards can create, update, or delete site-wide events.
4. **Isolated Panel Sessions**:
   - Board-only panel sessions (`PanelSession`) cannot view or modify personal calendars (returns `401 Unauthorized`).

---

## 3. Data Model & Database Schema

Table name: `calendar_events`

| Column | Type | Nullable | Constraints & Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Primary Key (`uuid4`) |
| `scope_kind` | `VARCHAR(32)` | No | `'site'`, `'workspace'`, or `'personal'` |
| `workspace_id`| `UUID` | Yes | Foreign Key to `workspaces.id` ON DELETE CASCADE |
| `owner_id` | `UUID` | Yes | Foreign Key to `users.id` ON DELETE CASCADE (set for personal) |
| `created_by` | `UUID` | No | Foreign Key to `users.id` ON DELETE RESTRICT |
| `title` | `VARCHAR(140)` | No | Title of event |
| `description`| `TEXT` | Yes | Detailed description or agenda |
| `location` | `VARCHAR(140)` | Yes | Venue, room, or link |
| `starts_at` | `TIMESTAMPTZ` | No | Event start time (stored in UTC, rendered in IST) |
| `ends_at` | `TIMESTAMPTZ` | No | Event end time (must be >= `starts_at`) |
| `all_day` | `BOOLEAN` | No | Default `FALSE`. If true, represents full date(s) |
| `color` | `VARCHAR(32)` | Yes | Hex color or palette key |
| `created_at` | `TIMESTAMPTZ` | No | Server timestamp default `now()` |
| `updated_at` | `TIMESTAMPTZ` | No | Server timestamp default `now()` |

### Check Constraints
- `ck_calendar_events_scope_kind`: `scope_kind IN ('site', 'workspace', 'personal')`
- `ck_calendar_events_time_order`: `starts_at <= ends_at`
- `ck_calendar_events_scope_target`:
  - `(scope_kind = 'personal' AND owner_id IS NOT NULL AND workspace_id IS NULL)` OR
  - `(scope_kind = 'workspace' AND workspace_id IS NOT NULL AND owner_id IS NULL)` OR
  - `(scope_kind = 'site' AND owner_id IS NULL AND workspace_id IS NULL)`

### Indexes
- `ix_calendar_events_time`: `(starts_at, ends_at)`
- `ix_calendar_events_workspace`: `(workspace_id, starts_at)`
- `ix_calendar_events_owner`: `(owner_id, starts_at)`
- `ix_calendar_events_scope`: `(scope_kind, starts_at)`

---

## 4. API Endpoints

All endpoints are registered under `/api/calendar`:

1. `GET /api/calendar/sources`
   - Returns the list of calendar layers available to the caller:
     - Personal calendar (`id: "personal"`, title: "My Calendar", color: `#d81b60`)
     - Site-wide calendar (`id: "site"`, title: "Institute Events", color: `#1565c0`)
     - Accessible workspaces (Divisions, Sections, Groups, Projects) with their roles and assigned colors.
2. `GET /api/calendar/events`
   - Parameters:
     - `start`: ISO 8601 string (required)
     - `end`: ISO 8601 string (required)
     - `sources`: Optional comma-separated list of calendar source IDs to filter
   - Logic:
     - Resolves caller's readable workspaces via `policy.readable_workspace_ids`.
     - Selects:
       - Site events overlapping `[start, end]`
       - Personal events where `owner_id = caller.id` overlapping `[start, end]`
       - Workspace events where `workspace_id IN readable_ids` overlapping `[start, end]`
3. `POST /api/calendar/events`
   - Body: `scope_kind`, `workspace_id` (if workspace), `title`, `description`, `location`, `starts_at`, `ends_at`, `all_day`, `color`
   - Validates authorization according to scope.
4. `GET /api/calendar/events/{event_id}`
   - Retrieves single event; returns 404 if out of scope.
5. `PATCH /api/calendar/events/{event_id}`
   - Updates title, description, location, timing, color. Enforces steward/creator/admin rules.
6. `DELETE /api/calendar/events/{event_id}`
   - Deletes event. Enforces steward/creator/admin rules.

---

## 5. UI Architecture & Components

Under `frontend/src/features/calendar/`:
- `types.ts`: TypeScript contracts for `CalendarEvent`, `CalendarSource`, and query payloads.
- `calendar.css`: Clean, professional Google Calendar styling with Indian Standard Time indicator, grid lines, today highlights, and color badges.
- `CalendarPage.tsx`: Main page housing the navigation bar, sidebar, and view views.
- `MonthView.tsx`: 7-day grid showing day numbers, multi-day event bars, and single-event chips.
- `WeekView.tsx`: 7-day time column view from 08:00 to 20:00 (with scroll for full 24h) and current IST time marker.
- `DayView.tsx`: Single-day hourly agenda view.
- `AgendaView.tsx`: Chronological stream of upcoming events grouped by date.
- `EventDialog.tsx`: Modal for creating and editing events with time pickers, scope selector, and color options.

---

## 6. Progress Ledger & Resume State

| Step | Task | Status | Notes |
| :--- | :--- | :--- | :--- |
| **1** | Write Specification & Progress Ledger | **DONE** | This document (`docs/CALENDAR_SPECIFICATION_AND_LEDGER.md`). |
| **2** | Alembic Migration `0042_calendar_events.py` & Model | **DONE** | Schema migration with upgrade and guarded downgrade. |
| **3** | Backend Router & Policy (`backend/labadda/api/calendar.py`) | **DONE** | Upward-only hierarchy queries & permissions. |
| **4** | Backend Regression Tests (`backend/tests/test_calendar.py`) | **DONE** | Tests for all scopes, denied cases, admin blindness, range queries. |
| **5** | Frontend Calendar UI & Views | **DONE** | Google-like Month, Week, Day, Agenda, Event Dialog, Sidebar. |
| **6** | Navigation & Routing | **DONE** | TopBar, RailNav, and `/calendar` route. |
| **7** | Documentation, Verification & Regression | **DONE** | `API.md`, in-app help, `check_docs.py`, backend & frontend tests. |

*Note for any successor agent: Check this ledger to see the active step and resume execution cleanly.*
