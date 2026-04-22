# IMPLEMENTATION PLAN — Data Intelligence Platform v2

> Written after reading SPEC.md and SPEC-v2.md in full and exploring the v1 codebase.
> All open questions resolved (see Section 2). Do not write production code until this plan is reviewed.

---

## 0. Codebase Inventory (What v1 Actually Has)

| Area | What Exists |
|---|---|
| **Users table** | `id`, `email`, `hashed_password`, `full_name`, `role` (admin/viewer enum), `is_active` (bool), `created_at`. Missing: `updated_at`, `status`, `created_by`, `updated_by`, `password_updated_at`, `theme_preference`, `last_selected_source_id`. |
| **Profile storage** | Single `profiles` table with JSON blobs: `statistics`, `null_rates`, `distributions`. No `column_profiles` table. `total_rows` / `total_columns` computed by ProfileAgent but **not persisted** (bug). |
| **ProfileAgent** | Computes per-column `min/max/mean/median/std/cardinality` (numeric) and `cardinality/top_values` (categorical). No `data_classification`, `pk_candidate`, `mode`, or column-type counts. |
| **AnomalyAgent** | Isolation Forest only. No z-score path. |
| **TrendAgent** | Uses all `np.number` columns as "numeric". No classification awareness. |
| **Celery** | Worker only (`celery_worker` service in docker-compose). `tasks.py` is a placeholder. No Celery Beat. |
| **Dashboard** | Layout is client-side React state only — no server persistence. Source selector renders but does not persist. Existing widgets: `kpi`, `trend`, `anomaly`, `forecast`, `profile`, `insights`. |
| **Connectors** | `BaseConnector`, `FileConnector`, `RestAPIConnector`, `registry.py`. Interface is clean. |
| **Auth** | JWT. `is_active` checked on login. Token stored in `sessionStorage` (lost on browser close). Self-service `/auth/register` and `RegisterPage` exist and remain in v2. |
| **Dark mode CSS** | `.dark` CSS variable block already defined in `index.css`. No toggle mechanism exists yet. |
| **Data source status enum** | `pending`, `active`, `error`. v2 needs `degraded`, `paused`, `disconnected` added. |

---

## 1. Resolved Decisions

| # | Question | Decision |
|---|---|---|
| Q1 | `column_profiles`: new table vs JSON blob | **JSON blob** — enrich existing `profiles.statistics` JSON per column |
| Q2 | `is_active` (bool) → `status` enum | **Replace** `is_active` with `status` enum (`active`/`disabled`). Find and update all code referencing `is_active` on `User`. |
| Q3 | Self-registration endpoint | **Keep** `/auth/register` and `RegisterPage` unchanged in v2. |
| Q4 | Token storage | **Move to `localStorage`** so sessions survive browser restart. |
| Q5 | `created_by`/`updated_by` nullable | **Nullable**, but **only** for the first registered user (bootstrap). Every subsequent user management action must supply a non-null actor. Enforced in code, not just by convention. |
| Q6 | Bell curve visualization | **True KDE** using `scipy.stats.gaussian_kde`. |
| Q7 | Default starter layout | Use the layout described in Phase 2 below. |
| Q8 | File connector re-poll behavior | **Re-read file at stored `config.file_path`** on each scheduled poll. If file is missing, mark source `degraded`. |
| Q9 | Card #5 scatter X-axis | **Row index by default; date column if one exists** in the source. |
| Q10 | Card #4 trend data storage | **Bake pre-aggregated time-series into `profiles.statistics`** JSON at profile time. No new endpoint. Profiles are regenerated on every poll, so cards automatically reflect the latest source state — the profile is the reactive data contract between source and cards. |
| Q11 | Z-score anomaly storage | **Add `zscore_anomalies` JSONB column to `profiles` table.** Confirmed. |

---

## 2. Assumptions

| # | Assumption |
|---|---|
| A1 | `total_rows` and `total_columns` added as explicit columns on `profiles` table (not buried in JSON). Fixes the existing persist bug. |
| A2 | `pk_candidate` = column is 100% non-null AND cardinality == total_rows. |
| A3 | `mode` for Card #3 = `Series.mode().iloc[0]`, or `null` if series is all-null or has no unique mode. |
| A4 | New v2 widget IDs: `data_profile`, `profile_details`, `descriptive_stats`, `trend_analysis`, `anomaly_detection`. Existing `forecast` and `insights` IDs preserved. |
| A5 | Schedule presets map to standard cron: 5min=`*/5 * * * *`, 15min=`*/15 * * * *`, hourly=`0 * * * *`, 6h=`0 */6 * * *`, daily=`0 0 * * *`, weekly=`0 0 * * 0`. |
| A6 | Celery Beat backed by `celery-redbeat` (Redis-backed schedule store). Avoids needing a filesystem-based celerybeat-schedule file and works cleanly in Docker. |
| A7 | IP address in audit log uses `request.client.host`, with `X-Forwarded-For` fallback. |
| A8 | Deactivated source in dropdown: replace bare `<select>` with shadcn `<Select>` (supports custom option rendering) showing "(Unavailable)" suffix and a visual badge. |
| A9 | `theme_preference` applied by toggling the `dark` class on `<html>` (Tailwind class-based dark mode). CSS variables in `index.css` already support this — no changes needed to that file. |
| A10 | Card #5 scatter: X = row_index (numeric), Y = selected column value. If a date column exists, X = date value. Points with `abs(z_score) > 3` rendered in a distinct highlight color. |
| A11 | Card #4 pre-aggregated time-series: for each (date_col, numeric_col) pair, ProfileAgent computes bucketed aggregates (max 500 points, auto-bucketed by date range: hourly/daily/weekly/monthly). Stored under `statistics[col]["time_series"][date_col]`. |
| A12 | 20-user cap from v1 was a spec statement only — no enforcement code exists in v1. No code change required to remove it. |

---

## 3. ProfileAgent Column Classification Logic

This section is called out separately because the spec and correction require non-trivial heuristics.

### Classification Rules (applied in order)

```
1. bool dtype                                     → categorical
2. object / string / categorical dtype            → categorical
3. datetime64 / timedelta dtype                   → continuous
4. int dtype:
     a. column name matches code pattern*         → discrete
     b. all other int columns                     → discrete
        (integers are inherently countable; no ratio override)
5. float dtype:
     a. column name matches code pattern*         → discrete
     b. unique_count ≤ DISCRETE_MAX_UNIQUE (20)   → discrete
     c. unique_ratio ≤ DISCRETE_MAX_RATIO (0.05)  → discrete
     d. otherwise                                  → continuous
6. fallback (any other dtype)                     → categorical
```

*Code pattern match: column name (lowercased, stripped) contains any of:
`_id`, `id_`, `\bid\b`, `zip`, `code`, `year`, `yr`, `iso`,
`fips`, `sku`, `num`, `no`, `nbr`, `pk`, `key`, `index`

Matched via a compiled regex: `r'\b(id|zip|code|year|yr|iso|fips|sku|num|no|nbr|pk|key|index)\b'`

### Thresholds

| Constant | Value | Rationale |
|---|---|---|
| `DISCRETE_MAX_UNIQUE` | 20 | A float column with ≤20 distinct values (e.g., ratings 1.0–5.0) is acting as ordinal/discrete |
| `DISCRETE_MAX_RATIO` | 0.05 | If fewer than 5% of rows are unique values, the column is not a true continuum |

### Examples

| Column name | dtype | unique_count | total_rows | → | Result |
|---|---|---|---|---|---|
| `revenue` | float64 | 800 | 1000 | | continuous |
| `rating` | float64 | 5 | 1000 | ≤20 unique | discrete |
| `score` | float64 | 45 | 1000 | 4.5% ratio | discrete |
| `customer_id` | int64 | 1000 | 1000 | name has `id` | discrete |
| `year` | int64 | 10 | 1000 | name is `year` | discrete |
| `quantity` | int64 | 50 | 1000 | | discrete |
| `created_at` | datetime64 | 500 | 1000 | | continuous |
| `is_active` | bool | 2 | 1000 | | categorical |
| `country_code` | object | 30 | 1000 | | categorical |

---

## 4. Phase Breakdown

---

### Phase 1 — Data Model Migrations

**Goal:** All new tables and columns exist before any backend logic changes. Migrations are additive and safe to apply against v1 data.

#### Migration `0002_v2_schema.py`

**`users` table changes:**
- Drop `is_active` (bool) and replace with `status` enum `('active', 'disabled')`. Migration: existing `is_active=true` rows → `status='active'`; `is_active=false` rows → `status='disabled'`.
- Add `updated_at` (DateTime, nullable)
- Add `created_by` (UUID, nullable FK → `users.id`, SET NULL on delete, no cascade)
- Add `updated_by` (UUID, nullable FK → `users.id`, SET NULL on delete, no cascade)
- Add `password_updated_at` (DateTime, nullable)
- Add `theme_preference` (Enum `'light'|'dark'|'system'`, NOT NULL, default `'light'`)
- Add `last_selected_source_id` (UUID, nullable FK → `data_sources.id`, SET NULL on delete)

**`data_sources` status enum extension:**
- Add `degraded`, `paused`, `disconnected` to the `sourcestatus` PostgreSQL enum via `ALTER TYPE sourcestatus ADD VALUE`.
- Note: Postgres enum additions are non-reversible. The downgrade path logs a warning and leaves the values in place.

**New table: `user_audit_log`**
```
id                UUID        PK
timestamp         DateTime    NOT NULL  default now()
actor_user_id     UUID        nullable  FK → users.id SET NULL
actor_email       String(255) NOT NULL
target_user_id    UUID        nullable  FK → users.id SET NULL
target_email      String(255) NOT NULL
action            Enum(create, modify_email, modify_role,
                       modify_status, reset_password, delete) NOT NULL
before_value      JSONB       nullable
after_value       JSONB       nullable
ip_address        String(45)  nullable
```
Indexes: `(actor_user_id, timestamp)`, `(target_user_id, timestamp)`, `(action, timestamp)`.

**New table: `user_dashboard_layouts`**
```
id          UUID     PK
user_id     UUID     NOT NULL  UNIQUE  FK → users.id CASCADE
layout      JSONB    NOT NULL  default '{}'
updated_at  DateTime NOT NULL  default now()
```

**New table: `source_schedules`**
```
id              UUID        PK
source_id       UUID        NOT NULL  UNIQUE  FK → data_sources.id CASCADE
schedule_expr   String(100) NOT NULL
enabled         Boolean     NOT NULL  default true
consecutive_failures Integer NOT NULL default 0
created_at      DateTime    NOT NULL  default now()
updated_at      DateTime    NOT NULL  default now()
created_by      UUID        nullable  FK → users.id SET NULL
```

**New table: `source_poll_log`**
```
id              UUID     PK
source_id       UUID     NOT NULL  FK → data_sources.id CASCADE
started_at      DateTime NOT NULL
completed_at    DateTime nullable
duration_ms     Integer  nullable
status          Enum('success', 'failure') NOT NULL
attempt_number  Integer  NOT NULL  default 1
error_message   Text     nullable
```
Index: `(source_id, started_at DESC)`.

#### Migration `0003_profile_v2_columns.py`

**`profiles` table changes:**
- Add `total_rows` (Integer, nullable)
- Add `total_columns` (Integer, nullable)
- Add `zscore_anomalies` (JSONB, nullable, default `'[]'`)

#### Model + Code Updates

| File | Change |
|---|---|
| `backend/app/models/user.py` | Add `UserStatus` enum; replace `is_active` with `status`; add all new columns; update `notifications` / `persist.py` references |
| `backend/app/models/data_source.py` | Add `degraded`, `paused`, `disconnected` to `SourceStatus` |
| `backend/app/models/profile.py` | Add `total_rows`, `total_columns`, `zscore_anomalies` |
| `backend/app/models/user_audit_log.py` | New model |
| `backend/app/models/user_dashboard_layout.py` | New model |
| `backend/app/models/source_schedule.py` | New model |
| `backend/app/models/source_poll_log.py` | New model |
| `backend/app/models/__init__.py` | Export new models |
| `backend/app/routers/auth.py` | Replace `user.is_active` check with `user.status == UserStatus.active` on login |
| `backend/app/agents/persist.py` | Replace `User.is_active == True` filter with `User.status == UserStatus.active` |

Search and update any other `is_active` references on `User` across the codebase before closing Phase 1.

#### Tests
- Migration applies cleanly against a fresh schema and against a populated v1 schema
- `is_active=true` rows migrate to `status='active'`; `is_active=false` → `status='disabled'`
- Login with a `status='disabled'` user returns 403
- All FK constraints on new tables verified

---

### Phase 2 — Account Management + Theme Infrastructure

**Goal:** Admin-only user CRUD with full audit log; theme toggle wired up globally.

#### 2a. Theme Infrastructure (implement first within this phase)

**`frontend/src/store/themeStore.ts`** (new):
```typescript
// Zustand store
// state: { theme: 'light' | 'dark' | 'system', resolvedTheme: 'light' | 'dark' }
// setTheme(t): updates state, writes `dark` class to document.documentElement,
//              calls PATCH /api/users/me/preferences (debounced 300ms)
// init(): reads theme from authStore user object on login; falls back to OS preference
//         if theme === 'system'
```

**`frontend/src/components/ThemeToggle.tsx`** (new):
- Sun / moon icon button. Calls `themeStore.setTheme()` on click.
- Cycles: light → dark → light (system preference can be set by OS on first login; once user explicitly toggles, explicit choice wins).

**`frontend/src/main.tsx`** — call `themeStore.init()` before first render to prevent flash of wrong theme.

**`frontend/src/store/authStore.ts`**:
- Move token from `sessionStorage` → `localStorage`.
- Include `theme_preference` in the stored `user` object (comes back from `/auth/login` response).

**`frontend/src/components/Navbar.tsx`**:
- Add `<ThemeToggle />` next to user email / logout.
- Add "Account Management" nav link, visible only when `user.role === 'admin'`.

#### 2b. Backend — User Management Endpoints

**`backend/app/routers/users.py`** (new file):

```
GET    /api/users                  Admin — list all users, sorted by created_at
POST   /api/users                  Admin — create user (email, password, role)
PATCH  /api/users/{id}             Admin — modify email, role, status, password
DELETE /api/users/{id}             Admin — hard delete user + their dashboard layout
GET    /api/users/audit-log        Admin — paginated, filterable audit log
GET    /api/users/me               Any authenticated — current user's profile
PATCH  /api/users/me/preferences   Any authenticated — update theme_preference,
                                              last_selected_source_id
```

**Shared helpers (within `users.py` or a `backend/app/services/user_service.py`):**

```python
async def assert_active_admin_remains(db, excluding_user_id: UUID) -> None:
    """Count active admins excluding the target. Raise 400 if count == 0."""

async def write_audit_log(
    db, actor_user_id, actor_email,
    target_user_id, target_email,
    action, before_value, after_value, ip_address
) -> None:
    """Insert a row into user_audit_log. actor_user_id may only be None
    when the system has zero users (bootstrap scenario). All other callers
    must pass a non-null actor_user_id — enforce with an assertion."""
```

**Business rules enforced server-side:**
- Duplicate email → 400 with clear message
- Delete/demote/disable last active admin → 400 "Cannot leave the system with no active Admin"
- Admin cannot delete/disable themselves if they are the last active admin
- Password hashed with bcrypt before storage; never returned in any response
- `audit_log` endpoint accepts optional query params: `actor_id`, `target_id`, `action`, `date_from`, `date_to`, `page`, `page_size` (default 50)

**`backend/app/routers/auth.py`** changes:
- `/auth/login` response includes `theme_preference` in the returned `user` object.
- No other changes (register route kept as-is per Q3).

**`backend/app/main.py`** — register `users.router` with prefix `/api`.

#### 2c. Frontend — Account Management Page

**`frontend/src/pages/AccountManagementPage.tsx`** (new):

Two tabs: **Users** | **Audit Log**.

*Users tab:*
- Table: Email, Role (badge), Status (badge: green=active, gray=disabled), Created At, Actions
- "New User" button → modal with Email, Password, Role fields
- Row actions: Edit (modal with Email, Role, Status, Reset Password fields), Delete (confirmation dialog surfacing the last-admin invariant error from the API as a friendly message)
- All mutations invalidate the users query via TanStack Query

*Audit Log tab:*
- Filter bar: Actor, Target, Action type, Date range
- Paginated table: Timestamp, Actor, Target, Action, Before, After, IP
- Before/After rendered as a collapsible JSON diff

**`frontend/src/App.tsx`**:
- Add `/account-management` route: authenticated users only; if role is `viewer`, render a `<ForbiddenPage />` component (not a redirect — user is logged in, just unauthorized).
- Route `/register` remains pointing to `RegisterPage` (unchanged).

**Default starter layout** (for new users, stored server-side and returned by `GET /api/dashboard/layout`):

```
Row 0-2  (h=3): [data_profile, w=4] [profile_details, w=8]
Row 3-6  (h=4): [descriptive_stats, w=6] [trend_analysis, w=6]
Row 7-10 (h=4): [anomaly_detection, w=6] [forecast, w=6]
Row 11-14 (h=4): [insights, w=12]
```
(12-column grid, rowHeight=80px)

#### New API Endpoints

| Method | Path | Auth |
|---|---|---|
| GET | `/api/users` | Admin |
| POST | `/api/users` | Admin |
| PATCH | `/api/users/{id}` | Admin |
| DELETE | `/api/users/{id}` | Admin |
| GET | `/api/users/audit-log` | Admin |
| GET | `/api/users/me` | Any |
| PATCH | `/api/users/me/preferences` | Any |

#### Tests
- Create user with duplicate email → 400
- Delete last active admin → 400
- Demote last active admin → 400
- Disable last active admin → 400
- Admin cannot delete themselves if last admin
- Viewer hitting `/api/users` → 403
- Viewer navigating to `/account-management` → ForbiddenPage (not redirect)
- Every mutating action produces an audit log entry with non-null actor fields (except bootstrap)
- Audit log filter by action type returns only matching rows
- Theme preference persists across logout/login cycle

---

### Phase 3 — Per-Source Polling Schedules (Celery Beat)

**Goal:** Admins configure per-source cron schedules; Celery Beat executes them; failures are tracked and trigger degraded state + admin notifications.

#### 3a. Backend — Schedule CRUD

Add to **`backend/app/routers/sources.py`**:

```
POST   /api/sources/{id}/schedule   Admin — create/upsert schedule
                                     body: {schedule_expr, enabled}
                                     validates cron via croniter before saving
GET    /api/sources/{id}/schedule   Admin — get current schedule config
DELETE /api/sources/{id}/schedule   Admin — remove schedule (manual-only mode)
GET    /api/sources/{id}/poll-log   Admin — paginated poll history
POST   /api/sources/{id}/refresh    Admin — enqueue immediate poll (ignores schedule)
```

On schedule create/update/delete: call `reload_beat_schedule(source_id)` (see 3b).

#### 3b. Backend — Celery Beat Integration

**`backend/app/tasks.py`** (replace placeholder):

```python
@celery_app.task(bind=True, max_retries=3)
def poll_source(self, source_id: str) -> None:
    """
    1. Write source_poll_log row (status=running, attempt_number=self.request.retries+1)
    2. Re-fetch source config from DB (source may have been updated since enqueue)
    3. Run run_pipeline(source_id, source_type, source_config) synchronously
    4. On success:
         - Update poll_log (status=success, duration_ms, completed_at)
         - Reset source_schedules.consecutive_failures = 0
         - If source.status == 'degraded': set to 'active'
    5. On failure:
         - Update poll_log (status=failure, error_message, completed_at)
         - Increment source_schedules.consecutive_failures
         - If consecutive_failures >= 3:
             set source.status = 'degraded'
             create Notification for all active Admins via NotificationAgent path
         - Retry with countdown: attempt 1→30s, attempt 2→120s, attempt 3→600s
         - After max retries exhausted: mark source 'disconnected' if error is
           auth/connection-level; otherwise leave as 'degraded'
    """
```

**`backend/app/beat_scheduler.py`** (new):

```python
def load_all_schedules() -> None:
    """Read all enabled source_schedules from DB and write to redbeat."""

def reload_beat_schedule(source_id: str) -> None:
    """Called after schedule CRUD — updates or removes a single redbeat entry."""

def get_beat_task_name(source_id: str) -> str:
    return f"poll_source:{source_id}"
```

Uses `redbeat.RedBeatSchedulerEntry` to register entries programmatically. Beat task name: `poll_source:<source_id>`.

**`backend/app/celery_app.py`** changes:
- Add `beat_scheduler = 'redbeat.RedBeatScheduler'`
- Add `redbeat_redis_url` pointing to `settings.REDIS_URL`

**`backend/app/main.py`** — on startup (`@app.on_event("startup")`), call `load_all_schedules()` to ensure Beat is in sync with the DB.

#### 3c. Source State Machine

```
pending     → active        : first successful poll or manual refresh
active      → degraded      : 3 consecutive scheduled poll failures
active      → paused        : Admin disables the schedule
degraded    → active        : any successful poll (scheduled or manual)
paused      → active        : Admin re-enables the schedule
any         → disconnected  : connector raises auth/connection-level exception
                              (requires Admin intervention to resolve)
```

`disconnected` sources do not receive scheduled polls until an Admin intervenes (e.g., by updating config and triggering a manual refresh).

#### 3d. Docker Compose

**`platform/docker-compose.yml`** — add `celery_beat` service:

```yaml
celery_beat:
  build:
    context: ./backend
    dockerfile: Dockerfile
  command: celery -A app.celery_app beat --scheduler redbeat.RedBeatScheduler --loglevel=info
  environment:
    DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://platform:changeme@db:5432/platform_db}
    REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
    JWT_SECRET: ${JWT_SECRET:-dev-secret-key}
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_started
  volumes:
    - ./backend:/app
  networks:
    - app-network
```

Mirror the same addition in **`docker-compose.prod.yml`**.

#### 3e. Frontend — Sources Page Updates

**`frontend/src/pages/SourcesPage.tsx`** additions:
- Status badge per source: active (green), degraded (orange + warning icon), paused (gray), disconnected (red), pending (blue)
- "Refresh Now" button (Admin only) → `POST /api/sources/{id}/refresh`
- Expandable schedule section (Admin only):
  - Preset dropdown: "Every 5 min", "Every 15 min", "Hourly", "Every 6 hours", "Daily", "Weekly"
  - "Advanced" toggle reveals a cron expression text input with inline validation feedback
  - Enable/Disable toggle
  - "Save Schedule" button
- "View Poll Log" link → slide-out `<Sheet>` with paginated table: Timestamp, Duration, Status, Attempt, Error

#### New Dependencies (Python)

| Package | Reason |
|---|---|
| `celery-redbeat` | Redis-backed Beat scheduler |
| `croniter` | Cron expression validation |

#### New API Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/api/sources/{id}/schedule` | Admin |
| GET | `/api/sources/{id}/schedule` | Admin |
| DELETE | `/api/sources/{id}/schedule` | Admin |
| GET | `/api/sources/{id}/poll-log` | Admin |
| POST | `/api/sources/{id}/refresh` | Admin |

#### Tests
- Valid cron expression → saved to `source_schedules`
- Invalid cron expression → 400 with validation message
- After 3 consecutive poll failures: `source.status == 'degraded'` + admin notifications created
- Successful poll after degraded: `status == 'active'`, `consecutive_failures == 0`
- Pausing schedule: source transitions to `paused`, no further scheduled polls enqueued
- Every poll attempt writes a `source_poll_log` row with correct status and duration
- Manual Refresh Now enqueues immediately regardless of schedule state
- `docker compose up` starts `celery_beat` service without errors

---

### Phase 4 — ProfileAgent Extensions + AnomalyAgent z-score

**Goal:** `ProfileAgent` emits column classification, `pk_candidate`, `mode`, KDE bell curve, and pre-aggregated time-series. `AnomalyAgent` gains z-score output path for Card #5.

#### 4a. ProfileAgent (`backend/app/agents/profile_agent.py`)

**New helpers to add:**

```python
# Classification constants
DISCRETE_MAX_UNIQUE = 20
DISCRETE_MAX_RATIO = 0.05
CODE_COLUMN_PATTERN = re.compile(
    r'\b(id|zip|code|year|yr|iso|fips|sku|num|no|nbr|pk|key|index)\b',
    re.IGNORECASE
)

def _classify_column(col_name: str, series: pd.Series, total_rows: int) -> str:
    """See Section 3 of this plan for full rules."""

def _compute_mode(series: pd.Series) -> Any:
    """Return mode value or None."""

def _compute_kde(series: pd.Series, n_points: int = 200) -> list[dict]:
    """Return [{x, y}] KDE curve using scipy.stats.gaussian_kde.
    Falls back to empty list if fewer than 5 non-null values."""

def _compute_time_series(
    df: pd.DataFrame, numeric_col: str, date_col: str, max_points: int = 500
) -> list[dict]:
    """Aggregate numeric_col against date_col.
    Auto-bucket: hourly if range ≤ 3 days, daily ≤ 90 days,
                 weekly ≤ 1 year, monthly otherwise.
    Returns [{date: isostring, value: float}]."""
```

**Per-column stats additions** (inside the existing `statistics[col]` dict):
- `data_classification`: `'categorical'` | `'discrete'` | `'continuous'`
- `pk_candidate`: `bool`
- `mode`: scalar or `null` (numeric and categorical columns)
- `kde`: `[{x, y}]` — numeric columns only (KDE curve)
- `time_series`: `{date_col_name: [{date, value}]}` — numeric columns only, one entry per date column found in the DataFrame

**Profile-level additions** (top-level `profile` dict):
- `total_rows`: int
- `total_columns`: int
- `categorical_count`: int
- `discrete_count`: int
- `continuous_count`: int

#### 4b. AnomalyAgent (`backend/app/agents/anomaly_agent.py`)

Add z-score detection **alongside** (not replacing) the existing Isolation Forest path:

```python
def _compute_zscore_anomalies(df: pd.DataFrame) -> list[dict]:
    """
    For each numeric column (discrete + continuous, using ProfileAgent classification
    if available in state, else all np.number columns):
      - Compute mean and std
      - Flag rows where abs((value - mean) / std) > 3
      - Return list of anomaly records with:
          row_index, column, value, z_score, mean, std,
          full_row (all column values for that row, safely serialized),
          detected_at
    """
```

Add `zscore_anomalies` to the returned state:
```python
return {**state, "anomalies": anomalies, "zscore_anomalies": zscore_anomalies, ...}
```

#### 4c. AgentState (`backend/app/agents/state.py`)

Add:
```python
zscore_anomalies: list[dict]
```

#### 4d. Persist (`backend/app/agents/persist.py`)

Update `Profile` persist to write:
- `total_rows`, `total_columns` from `profile_data`
- `zscore_anomalies` from `state.get("zscore_anomalies", [])`

#### 4e. Profiles Router (`backend/app/routers/profiles.py`)

- Enrich `GET /profiles/{source_id}` response to include `total_rows`, `total_columns`, classification counts, and per-column `data_classification`, `pk_candidate`, `mode`, `kde`, `time_series`.
- Add `GET /api/profiles/{source_id}/anomalies?column=<col>` — filters `zscore_anomalies` from the latest profile for the given column. If `column` param omitted, returns anomalies across all columns.

#### Files Modified in Phase 4

| File | Change |
|---|---|
| `backend/app/agents/profile_agent.py` | Classification, pk_candidate, mode, KDE, time-series, counts |
| `backend/app/agents/anomaly_agent.py` | Add z-score path, emit `zscore_anomalies` |
| `backend/app/agents/state.py` | Add `zscore_anomalies` |
| `backend/app/agents/persist.py` | Persist new profile fields and zscore_anomalies |
| `backend/app/models/profile.py` | Already updated in Phase 1 migration |
| `backend/app/routers/profiles.py` | Enrich response; add anomalies endpoint |

#### Tests
- `bool` column → `categorical`
- `object` column → `categorical`
- `datetime64` column → `continuous`
- `int64` column named `customer_id` → `discrete` (name match)
- `int64` column named `quantity` → `discrete` (int default)
- `float64` column with 5 unique values → `discrete` (≤ DISCRETE_MAX_UNIQUE)
- `float64` column with unique_ratio = 0.03 → `discrete` (≤ DISCRETE_MAX_RATIO)
- `float64` column with unique_ratio = 0.80 → `continuous`
- `pk_candidate = true` only when null_rate == 0 and cardinality == total_rows
- Z-score flags a value at mean + 3.1σ; does not flag mean + 2.9σ
- `zscore_anomalies` includes `full_row` with all column values for flagged rows
- KDE returns 200 points when ≥5 non-null values; empty list otherwise
- Profile-level counts sum to `total_columns`

---

### Phase 5 — Dashboard Enhancements

**Goal:** Per-user server-side layout persistence; source dropdown with last-selected persistence and deactivated source handling.

#### 5a. Backend — Dashboard Layout Endpoints

**`backend/app/routers/dashboard.py`** (new file):

```
GET /api/dashboard/layout   — Return current user's layout from user_dashboard_layouts.
                              If no row exists (new user), return the hardcoded default
                              starter layout (see Phase 2).
PUT /api/dashboard/layout   — Upsert layout for current user. Body: {grid, widget_state}.
                              Creates or updates the user_dashboard_layouts row.
```

Layout JSON schema:
```json
{
  "grid": [
    {"i": "data_profile", "x": 0, "y": 0, "w": 4, "h": 3},
    ...
  ],
  "widget_state": {
    "descriptive_stats": {"selected_column": "revenue"},
    "trend_analysis": {
      "selected_column": "revenue",
      "selected_date_column": "created_at"
    },
    "anomaly_detection": {"selected_column": "revenue"}
  }
}
```

**`backend/app/main.py`** — register `dashboard.router`.

#### 5b. Frontend — Dashboard Store

**`frontend/src/store/dashboardStore.ts`** (new):
```typescript
interface DashboardStore {
  layout: Layout[]
  widgetState: Record<string, Record<string, string>>
  selectedSourceId: string | null
  isLoaded: boolean
  fetchLayout: () => Promise<void>      // GET /api/dashboard/layout on login
  saveLayout: (layout, widgetState) => void  // debounced 500ms PUT
  setSelectedSource: (id: string) => void    // updates store + PATCH /api/users/me/preferences
  setWidgetState: (widgetId, key, value) => void  // updates + triggers debounced save
}
```

On login: call `fetchLayout()` which sets `layout`, `widgetState`, and initializes `selectedSourceId` from `user.last_selected_source_id`.

#### 5c. Frontend — DashboardPage Refactor

**`frontend/src/pages/DashboardPage.tsx`** changes:
- Replace `useState<Layout[]>` with `dashboardStore.layout`
- Replace bare `<select>` with shadcn `<Select>` component
- Source dropdown behavior:
  - For each source: if `source.is_active === false` (deactivated by Admin), render option with `(Unavailable)` label in a muted color and a badge
  - If `selectedSourceId` resolves to an unavailable source: show banner on Cards #1–#5: "This source is no longer available. Please select a different source."
  - If `selectedSourceId` resolves to a source not found in the list at all (deleted): same banner
  - Once user picks an active source: banner clears, `setSelectedSource()` called
- Widget rendering: if a widget's source was deleted, render `<EmptyState>` with "Source no longer available" + "Remove widget" action
- Pass `widgetState[widgetId]` to each card component

**Empty state messages by scenario:**

| Scenario | Admin message | Viewer message |
|---|---|---|
| No sources exist | "Add a data source to get started" | "Ask your Admin to add a data source" |
| Source unavailable/deleted | "This source is no longer available. Select a different source." | (same) |
| Source exists, no profile yet | "Analysis in progress…" | (same) |

#### New API Endpoints

| Method | Path | Auth |
|---|---|---|
| GET | `/api/dashboard/layout` | Any authenticated |
| PUT | `/api/dashboard/layout` | Any authenticated |

#### Tests
- New user `GET /api/dashboard/layout` → returns default starter layout
- `PUT` then logout + login → layout restored
- Last-selected source restored from `users.last_selected_source_id`
- Source marked inactive → shown with Unavailable badge; cards show banner
- Deleted source ID → same banner
- Selecting a new active source clears banner and persists the selection

---

### Phase 6 — Card Redesigns (#1–#5)

**Goal:** Implement the five redesigned analytical cards per SPEC-v2 Section 4.5.

All five cards live under `frontend/src/components/cards/`. Each receives `sourceId: string` and `widgetState: Record<string, string>` props. Each card manages its own TanStack Query fetches.

#### Card #1 — Data Profile (`DataProfileCard.tsx`)

**Data source:** `GET /profiles/{source_id}`

**Renders:**
- Title: "Data Profile"
- Six stat chips in a 2×3 or 3×2 grid: Rows, Columns, Categorical, Discrete, Continuous
- No interaction. Auto-refreshes via `refetchInterval: 30_000`.

**Empty state:** If `profile` is null, render "Analysis in progress…" placeholder.

---

#### Card #2 — Profile Details (`ProfileDetailsCard.tsx`)

**Data source:** `GET /profiles/{source_id}`

**Renders:**
- Search input (filters by column name, client-side)
- Sortable table:

| Column | Data Type | Null Rate | Cardinality | PK Candidate | Classification |
|---|---|---|---|---|---|
| string | string | `%` formatted | int | ✓ / — | colored badge |

- Classification badge colors: categorical=gray, discrete=blue, continuous=green
- Sorting: click column header to toggle asc/desc
- Table uses shadcn `<Table>` with client-side sort/filter (all data already loaded)

---

#### Card #3 — Descriptive Statistics (`DescriptiveStatsCard.tsx`)

**Data source:** `GET /profiles/{source_id}`

**Column dropdown logic:**
```typescript
const numericCols = columns.filter(c => c.classification !== 'categorical')
const defaultCol = numericCols.find(c => c.classification === 'discrete')
                ?? numericCols[0]
                ?? null
```
Persisted via `widgetState["descriptive_stats"]["selected_column"]`.

**Renders:**
- Column dropdown
- Five stat chips: min, max, std, mean, mode
- Distribution chart: Recharts `ComposedChart`
  - `Bar` series: histogram buckets from `distributions[col]` (existing data)
  - `Line` series: KDE curve from `statistics[col].kde`
  - `ReferenceLine` annotations at: mean (solid), mean±σ (dashed), mean±2σ (dashed), mean±3σ (dotted)
  - Reference lines labeled inline on the chart

---

#### Card #4 — Trend Analysis (`TrendAnalysisCard.tsx`)

**Data source:** `GET /profiles/{source_id}`

**Column dropdown logic:** same as Card #3 — numeric columns, default to first discrete.

**Date column logic:**
- Identify date columns: `statistics[col].data_classification === 'continuous'` AND `dtype` contains `'datetime'`
- If 0 date columns → empty state: "Trend analysis requires a date/time column in your dataset."
- If 1 date column → use it automatically
- If 2+ date columns → show secondary "Date Column" dropdown

**Persisted state:** `selected_column`, `selected_date_column` in `widgetState["trend_analysis"]`.

**Renders:**
- Column dropdown + optional date column dropdown
- Recharts `LineChart` with `Line` for the selected numeric column vs date
- Data: `statistics[col].time_series[date_col]` array
- X-axis: formatted dates. Y-axis: numeric values.
- Auto-aggregation bucket shown in chart subtitle (e.g., "Aggregated weekly")

---

#### Card #5 — Anomaly Detection (`AnomalyDetectionCard.tsx`)

**Data sources:**
- `GET /profiles/{source_id}` (column list, stats)
- `GET /profiles/{source_id}/anomalies?column=<col>` (z-score anomaly records)

**Column dropdown logic:** same as Cards #3–#4.

**Persisted state:** `selected_column` in `widgetState["anomaly_detection"]`.

**Views (tab or toggle):**

*Summary view (default):*
- Count chip: "X anomalies detected (values > 3σ from mean)"
- Scrollable list: each flagged row shows row_index, value, z_score formatted as `±N.Nσ`

*Scatter plot view:*
- Recharts `ScatterChart`
  - All data points from `statistics[col].time_series` or row-index enumeration (if no date col)
  - Normal points: muted color
  - Flagged points (abs(z_score) > 3): accent/highlight color (red in light mode, orange in dark)
  - Tooltip on hover: row index, value, z-score

*Audit panel:*
- "Audit" button → shadcn `<Sheet>` (slide-in side panel)
- Table: one row per flagged anomaly
  - Columns: Row Index, [all columns from `full_row`], Z-Score
  - Flagged column value highlighted in the row
- Read-only. No actions (export, mark false-positive deferred to future spec).

---

#### Widget Map Update (`DashboardPage.tsx`)

Replace old widget map:
```typescript
// Remove: kpi, trend, anomaly, profile (v1 widgets)
// Add:
data_profile      → <DataProfileCard sourceId={activeSource} widgetState={ws["data_profile"]} />
profile_details   → <ProfileDetailsCard sourceId={activeSource} ... />
descriptive_stats → <DescriptiveStatsCard sourceId={activeSource} ... />
trend_analysis    → <TrendAnalysisCard sourceId={activeSource} ... />
anomaly_detection → <AnomalyDetectionCard sourceId={activeSource} ... />
// Unchanged:
forecast          → <ForecastWidget insights={insights} />
insights          → <InsightFeed insights={insights} />
```

#### New/Modified API Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/profiles/{id}` | Any | Enriched with all Phase 4 additions |
| GET | `/api/profiles/{id}/anomalies` | Any | Z-score anomalies, filterable by `?column=` |

#### Tests
- Card #1: stat counts match classification counts from profile
- Card #2: search for "rev" returns only columns containing "rev"; sort by null_rate ascending works
- Card #3: defaults to first discrete column; falls back to first continuous when no discrete exists; KDE curve renders (non-empty `kde` data)
- Card #4: no-date-column source renders empty state; multiple date columns show secondary dropdown; trend line renders from time_series data
- Card #5: summary count matches anomaly records; scatter shows all points + highlights; audit panel lists full row contents with flagged column highlighted

---

### Phase 7 — Light/Dark Mode Completion Pass

**Goal:** Verify every component added in Phases 2–6 renders correctly in both themes. The toggle infrastructure was set up in Phase 2; this phase is a targeted audit-and-patch.

#### What to audit

| Area | What to check |
|---|---|
| All pages | Dashboard, Account Management, Sources (schedule UI), Login, Register, Agent Log |
| Modals/panels | Create User, Edit User, Anomaly Audit Sheet, Poll Log Sheet, confirmation dialogs |
| Cards #1–#5 | Stat chips, tables, dropdowns, badges |
| Charts | Bell curve (Card #3), trend line (Card #4), scatter plot (Card #5) |
| Navbar | Theme toggle button, notification bell, user menu |

#### Common issues to fix

- Hardcoded colors like `bg-red-50 text-red-800` → replace with semantic classes (`bg-destructive/10 text-destructive`) or add `dark:` variants
- Recharts SVG colors: define a `useChartColors()` hook that returns theme-appropriate hex values for chart strokes and fills. Recharts does not read CSS variables directly in SVG attributes — the hook reads the current `resolvedTheme` from `themeStore` and returns appropriate values.
- Reference line labels: ensure they have sufficient contrast in both themes
- Badge and status indicator backgrounds verified in dark mode

#### Implementation approach

```typescript
// frontend/src/hooks/useChartColors.ts (new)
export function useChartColors() {
  const { resolvedTheme } = useThemeStore()
  const isDark = resolvedTheme === 'dark'
  return {
    primary:    isDark ? '#60a5fa' : '#3b82f6',
    muted:      isDark ? '#94a3b8' : '#cbd5e1',
    anomaly:    isDark ? '#f97316' : '#ef4444',
    kde:        isDark ? '#a78bfa' : '#8b5cf6',
    refLine:    isDark ? '#475569' : '#94a3b8',
    gridLine:   isDark ? '#1e293b' : '#e2e8f0',
  }
}
```

#### Tests
- Toggling theme applies `dark` class to `<html>` immediately (no page reload)
- Theme preference sent to `PATCH /api/users/me/preferences` after toggle
- After logout + login: theme restored from server preference
- All chart colors pass minimum contrast ratio (WCAG AA) in both themes — verify manually or via automated contrast check

---

## 5. File Summary

### New Backend Files

| File | Phase |
|---|---|
| `backend/alembic/versions/0002_v2_schema.py` | 1 |
| `backend/alembic/versions/0003_profile_v2_columns.py` | 1 |
| `backend/app/models/user_audit_log.py` | 1 |
| `backend/app/models/user_dashboard_layout.py` | 1 |
| `backend/app/models/source_schedule.py` | 1 |
| `backend/app/models/source_poll_log.py` | 1 |
| `backend/app/routers/users.py` | 2 |
| `backend/app/routers/dashboard.py` | 5 |
| `backend/app/beat_scheduler.py` | 3 |

### Modified Backend Files

| File | Phases | What Changes |
|---|---|---|
| `backend/app/models/user.py` | 1 | `UserStatus` enum; replace `is_active`; add 7 new columns |
| `backend/app/models/data_source.py` | 1 | Add `degraded`, `paused`, `disconnected` to `SourceStatus` |
| `backend/app/models/profile.py` | 1 | Add `total_rows`, `total_columns`, `zscore_anomalies` |
| `backend/app/models/__init__.py` | 1 | Export new models |
| `backend/app/routers/auth.py` | 1 | Switch `is_active` → `status` check; include `theme_preference` in login response |
| `backend/app/routers/sources.py` | 3 | Add schedule/poll-log/refresh endpoints; update status badge data |
| `backend/app/routers/profiles.py` | 4, 6 | Enrich response; add anomalies endpoint |
| `backend/app/agents/profile_agent.py` | 4 | Classification, pk_candidate, mode, KDE, time-series, counts |
| `backend/app/agents/anomaly_agent.py` | 4 | Add z-score path |
| `backend/app/agents/state.py` | 4 | Add `zscore_anomalies` |
| `backend/app/agents/persist.py` | 1, 4 | Fix `is_active` ref; persist new profile fields |
| `backend/app/celery_app.py` | 3 | Add redbeat scheduler config |
| `backend/app/tasks.py` | 3 | Replace placeholder with `poll_source` task |
| `backend/app/main.py` | 2, 3, 5 | Register new routers; startup schedule load |
| `platform/docker-compose.yml` | 3 | Add `celery_beat` service |
| `platform/docker-compose.prod.yml` | 3 | Add `celery_beat` service |

### New Frontend Files

| File | Phase |
|---|---|
| `frontend/src/store/themeStore.ts` | 2 |
| `frontend/src/store/dashboardStore.ts` | 5 |
| `frontend/src/components/ThemeToggle.tsx` | 2 |
| `frontend/src/pages/AccountManagementPage.tsx` | 2 |
| `frontend/src/components/cards/DataProfileCard.tsx` | 6 |
| `frontend/src/components/cards/ProfileDetailsCard.tsx` | 6 |
| `frontend/src/components/cards/DescriptiveStatsCard.tsx` | 6 |
| `frontend/src/components/cards/TrendAnalysisCard.tsx` | 6 |
| `frontend/src/components/cards/AnomalyDetectionCard.tsx` | 6 |
| `frontend/src/hooks/useChartColors.ts` | 7 |

### Modified Frontend Files

| File | Phases | What Changes |
|---|---|---|
| `frontend/src/store/authStore.ts` | 2 | `sessionStorage` → `localStorage`; add `theme_preference` to stored user |
| `frontend/src/components/Navbar.tsx` | 2 | Add `<ThemeToggle>`; add Admin-only "Account Management" link |
| `frontend/src/App.tsx` | 2 | Add `/account-management` route; add `<ForbiddenPage>` |
| `frontend/src/pages/DashboardPage.tsx` | 5, 6 | Layout from store; new widget map; shadcn Select; empty states |
| `frontend/src/pages/SourcesPage.tsx` | 3 | Schedule UI; status badges; Refresh Now; poll log sheet |
| `frontend/src/main.tsx` | 2 | Apply initial theme class before first render |

---

## 6. New Python Dependencies

| Package | Phase | Reason |
|---|---|---|
| `celery-redbeat==2.0.0` | 3 | Redis-backed Celery Beat scheduler (Docker-friendly) |
| `croniter==2.0.1` | 3 | Cron expression validation |
| `scipy==1.12.0` | 4 | `gaussian_kde` for bell curve. Already a transitive dep of `ydata-profiling` and `prophet` — now pinned explicitly in `requirements.txt`. |

No new npm packages required — all UI uses existing Recharts + shadcn/ui stack.

---

## 7. Non-Functional Notes

**Indexes added in migration:**
- `user_audit_log`: `(actor_user_id, timestamp)`, `(target_user_id, timestamp)`, `(action, timestamp)`
- `source_poll_log`: `(source_id, started_at DESC)`

**Audit log is append-only:** No `DELETE` or `UPDATE` endpoints are exposed for `user_audit_log`. This is intentional — immutability is a requirement.

**Security:**
- Admin-only routes enforced server-side via `require_admin` dep. UI hiding is cosmetic only.
- Passwords never returned in any response body.
- `created_by` / `updated_by` nullability constraint: the application layer must assert `actor_user_id is not None` before writing audit log entries for any non-bootstrap operation.

**Backward compatibility of profiles endpoint:**
- The Phase 4 enrichments are additive to the JSON response. Existing frontend code reading `statistics`, `null_rates`, `distributions` will continue to work. New fields appear alongside old ones.
