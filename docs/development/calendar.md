# Calendar System

The LabAdda Central Calendar provides full-fidelity scheduling across personal, workspace,
and site-wide institutional scopes, integrating tightly with the laboratory hierarchy while
maintaining strict administrator content blindness.

## 1. Scope and Access Model

| Scope | Visibility | Write Permission | Admin Access |
| --- | --- | --- | --- |
| `personal` | Owner only | Owner only | **None** (blindness rule) |
| `workspace` | Upward-only unit hierarchy and direct project members | Workspace members with write policy | None unless a direct member |
| `site` | All active intranet users | Site administrators & root stewards | Manage site notices & institute calendar |

- **Upward-only hierarchy**: A member of a Section sees events from their Section, parent
  Division, parent Group, and Root. A parent Division member cannot see child Section events.
- **Projects and Groups**: Flat and strictly private to invited participants.
- **Admin Blindness**: Administrators see metadata/counts only. Querying personal events
  belonging to another user returns a uniform `404 Not Found`.

## 2. Minimal Source Path

- **Backend API**: `backend/labadda/api/calendar.py`
- **Database Schema**: `backend/labadda/models.py` (`CalendarEvent`), migration `0042_calendar_events.py`
- **Frontend Views & Components**: `frontend/src/features/calendar/`
  - `MonthView.tsx`, `WeekDayView.tsx`, `AgendaView.tsx`, `EventDialog.tsx`, `CalendarSidebar.tsx`
- **Frontend Page & Route**: `frontend/src/pages/CalendarPage.tsx` (`/calendar`)
- **Help Center**: `frontend/src/help/using/calendar.md`

## 3. Verification

```bash
# Backend unit & authorization tests (including denied cases)
./.venv/bin/python -m pytest backend/tests/test_calendar.py -q

# Frontend production build & tests
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Timed events now deliver in-app reminders fifteen minutes before starting; see
[notification delivery](alert-preferences.md#live-pop-ups). All-day/cancelled events are excluded.
