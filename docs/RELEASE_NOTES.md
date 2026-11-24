# LabAdda Office Rollout Release Notes

**Target Deployment:** Monday Morning Intranet Rollout  
**Environment:** Air-gapped Intranet (Single Ubuntu VM, PostgreSQL, FastAPI, React)  
**Database Migration Head:** `0041_multi_board_and_profile_fields`  
**Timezone:** Indian Standard Time (IST, `Asia/Kolkata`, UTC+5:30)

---

## 1. Executive Summary

This release packages major user experience, collaboration, and administration enhancements to prepare LabAdda for full operational office rollout on Monday morning. The update expands the whiteboard capability to support multiple tabbed boards per scope, brings a familiar WhatsApp-like chat experience, introduces a public intranet staff directory with keyword and specialization discovery, enables self-service profile maintenance and avatar photo uploads, delivers a model CSV template for bulk staff onboarding, enforces Indian Standard Time (IST) across the entire platform, and establishes actionable user-friendly error reporting with rich diagnostic server logging.

---

## 2. Key Features & Enhancements

### 2.1 Multi-Tabbed Whiteboards Across All Levels
Research teams frequently conduct parallel discussions on experimental setups, equipment calibrations, and theoretical models. A single whiteboard can quickly become cluttered.
- **Tabbed Whiteboards Everywhere:** Every scope—Groups, Divisions, Sections, and Personal Workspaces—now supports multiple independent whiteboard tabs (`Board 1`, `Board 2`, etc.).
- **Custom Tab Titles:** Users can rename tabs inline to describe their purpose (e.g., "Vacuum Setup", "XRD Analysis").
- **State & Revision Isolation:** Each board tab maintains its own independent epoch, revision sequence, undo/redo stack, and snapshot history. Actions on Board 2 never interfere with Board 1.
- **Configurable Limit:** To maintain optimal database and rendering performance, the maximum number of whiteboards allowed per scope is configurable by site administrators (`GET/PATCH /admin/settings/whiteboards`), defaulting to **5**.
- **Touch Panel & Security:** Strict access boundary checks guarantee that whiteboard access respects existing workspace permissions and hierarchy rules.

### 2.2 WhatsApp-Style Modern Chat Interface
The chat interface has been redesigned to provide a friendly, intuitive messaging experience modeled after WhatsApp desktop/web:
- **Visual Theme:** WhatsApp doodle wallpaper SVG background with authentic messaging bubble geometry.
- **Incoming vs. Outgoing Messages:**
  - Outgoing messages appear on the right in light-green bubbles (`#d9fdd3`) with IST timestamp and double blue checkmarks (`✓✓`).
  - Incoming messages appear on the left in clean white bubbles (`#ffffff`) with sender identity and IST timestamp.
- **Date Separator Badges:** Floating date badges ("Today", "Yesterday", day of the week, or IST date) cleanly segment chat sessions.
- **Quoted Message Replies:** Direct message replying with colored sender accent border, snippet preview, and instant scroll-to-reference.
- **Composer Toolbar:** Quick-access attachment button (`+`), emoji shortcut bar (`😊`), rounded message input pill ("Type a message"), and send/mic action button.
- **In-Chat Header & Search:** Integrated chat header displaying workspace/colleague identity, online indicator, call/video/search icons, and real-time in-chat keyword search.

### 2.3 Model CSV Reference Template for Staff Onboarding
To streamline office onboarding of scientists, engineers, and administrative personnel:
- **Reference Template:** Created `fixtures/staff_import_model.csv` and `docs/staff_import_reference.csv` populated with realistic Indian research laboratory data (National Metallurgy & Surface Engineering Laboratory, divisions, sections, designations, and employee codes).
- **One-Click Download:** Administrators can download the reference CSV template directly from the Staff Import dialog in the web app or via `GET /admin/changes/import/staff/template?format=csv`.
- **Validation Guidance:** Built-in column descriptions and guidance prevent common import formatting mistakes (e.g. invalid unit hierarchy, missing identifiers).

### 2.4 User-Friendly Error Messages & Diagnostic Logging
- **Actionable Corrective Errors:** Generic error codes have been replaced with clear, informative messages that tell users what went wrong and how to fix it. For example:
  - *Previous:* `"Error: File too large to upload"`
  - *Current:* `"Error: File too large to upload; max upload size permitted is 20MB. Please select a smaller file."`
- **Contextual Diagnostic Logging:** Server errors capture detailed contextual diagnostics (`endpoint`, `method`, `request_id`, `user`, `status`, exception type, and stack trace) in structured application logs. This enables operators to diagnose and resolve office intranet issues rapidly without exposing technical internals to end users.

### 2.5 Local Indian Standard Time (IST) Everywhere
- **Default Application Timezone:** All timestamps, notice deadlines, chat times, whiteboard timestamps, and audit events are configured to Indian Standard Time (`Asia/Kolkata`, UTC+5:30).
- **Consistent Clock Formatting:** Consistent 12-hour AM/PM formatting (e.g. `7:55 pm`) and date grouping across both frontend components and backend services.

### 2.6 Staff Directory & Colleague Discovery
- **Dedicated Staff Directory (`/directory`):** A clean intranet directory where staff can search and discover colleagues.
- **Advanced Search Filters:** Search across full name, display name, designation, specialization keywords (e.g., "Nanocoatings", "Thin Films", "Spectroscopy"), mobile number, email, and division/section units.
- **Privacy Compliance:** Contact details and specializations are accessible to authenticated intranet colleagues, while `/admin/people` bulk administrative tables remain strictly compliant with privacy regulations (no contact leakage in administrative dashboards).

### 2.7 Self-Service Profile Customization & Profile Pictures
- **Self-Editable Fields:** Staff can maintain their own contact and research details via `/profile`:
  - Display Name (defaults to Full Name / Username)
  - Designation (e.g., Senior Scientist, Technical Officer)
  - Field of Specialization (comma-separated keywords)
  - Office Phone / Extension
  - Mobile Number
  - Alternate Email Address
- **Profile Picture (Avatar) Upload:** Users can upload their profile photo (PNG, JPEG, WebP) directly in the browser or clear it anytime. Photos are safely encoded, validated (max 500KB), and rendered with initials fallback.

---

## 3. Database Migration Summary

Migration: `backend/migrations/versions/0041_multi_board_and_profile_fields.py`
- `system_settings` table: Key-value store for runtime settings (`max_whiteboards_per_scope`, default `5`).
- `users` table: Added `mobile`, `alternate_email`, `specialization`, and `avatar_data`.
- `boards` table: Retained primary key `workspace_id` for Board 0; added `title` VARCHAR(64).
- `workspace_boards` table: Stores secondary boards (`board_index >= 1`) with foreign key cascade to `workspaces`.
- `board_ops` & `board_snapshots`: Added `board_index` INT DEFAULT 0 with composite indices.
- `personal_board_revisions`: Added `board_index` and `title`.
- **Downgrade Tested:** Confirmed lossless downgrade and upgrade procedures.

---

## 4. Verification & Testing

All features have been validated with targeted test suites and strict quality checks:
1. **Regression Test Suites:**
   - `test_workspace_boards.py`: Tab creation, renaming, stroke isolation, non-admin limit updates, and 404 outsider denial.
   - `test_personal_board.py`: Personal tabbed boards, independent revisions, and data isolation.
   - `test_me.py`: Profile self-editing, avatar upload, and removal.
   - `test_people_directory.py`: Specialization keywords, designation, and contact search across intranet staff.
   - `test_staff_import.py`: Model reference CSV download, headers, and preview verification.
   - `test_files.py`: Actionable file upload size limit error message validation.
2. **Frontend Typecheck & Build:**
   - `npm run typecheck`: 0 errors.
   - `npm run build`: 407 modules built cleanly.
3. **Documentation Consistency:**
   - `python scripts/check_docs.py`: OK.

---

## 5. Monday Morning Rollout Checklist for System Operators

Follow this procedure when executing the rollout on the office server:

1. **Pre-Deployment Backup:**
   ```bash
   sudo -u postgres pg_dump -Fc labadda_production > /var/backups/labadda_pre_rollout_$(date +%F_%H%M).dump
   ```
2. **Fetch Latest Code:**
   ```bash
   cd /opt/labadda
   git pull --ff-only origin main
   ```
3. **Apply Database Migration:**
   ```bash
   cd backend && ../.venv/bin/alembic upgrade head
   ```
4. **Build Frontend Bundle:**
   ```bash
   cd ../frontend && npm ci && npm run build
   ```
5. **Restart Service & Verify Health:**
   ```bash
   sudo systemctl restart labadda
   curl -f http://127.0.0.1:8000/healthz
   curl -f http://127.0.0.1:8000/readyz
   ```
6. **Post-Rollout Smoke Test:**
   - Sign in as an administrator.
   - Verify Whiteboards tab switching (create and rename "Board 2").
   - Test WhatsApp-style chat bubble and timestamp display (confirm IST time).
   - Navigate to `/directory` and perform a search.
   - Visit `/profile`, upload an avatar, and update specialization keywords.
   - Check Staff Import dialog and confirm "Download CSV template" generates valid CSV.
