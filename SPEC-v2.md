# SPEC.md — Data Intelligence Platform (v2)

---

## 1. Vision

The v1 vision is unchanged: an autonomous, agent-powered data intelligence platform that connects to data sources, learns from their patterns over time, and proactively surfaces insights via a real-time dashboard.

**v2 focus:** operationalize the platform for real, multi-user teams and sharpen the core profiling and analytical cards that users interact with every day. Specifically, v2 gives Admins direct control over who uses the system and how often data is refreshed, makes the dashboard feel personal and durable, and tightens the definition and behavior of the primary analytical cards.

---

## 2. What We ARE Building (v2)

### 2.1 New Features

| Feature | Description |
|---|---|
| **Account Management** | Admin-only page (accessible from header menu) to create, modify, and delete users regardless of role. |
| **Per-Source Polling Schedules** | Admins can configure the frequency or schedule at which each connected data source is polled/queried, triggering agents to recompute profiling metrics. |
| **Light / Dark Mode** | Any user can toggle the app UI between light and dark themes. Preference persists across sessions. |

### 2.2 Enhancements to Existing Functionality

| Enhancement | Description |
|---|---|
| **Per-user dashboard layout** | Each user now has their own private dashboard layout that persists across sessions. |
| **Source-scoped dashboard** | A data source dropdown at the top of the Dashboard page drives what every card renders. |
| **Card #1 — Data Profile** | Redesigned as a summary card showing row count, column count, and column-type breakdown (categorical / discrete / continuous). |
| **Card #2 — Profile Details** | Tabular per-column view: column, data type, null rate, cardinality, PK-candidate flag, data classification. |
| **Card #3 — Descriptive Statistics** | Column dropdown (numeric fields only), min/max/std/mean/mode, and a distribution bell curve with stats called out. |
| **Card #4 — Trend Analysis** | Column dropdown (numeric fields only), plotted against a date/time axis. |
| **Card #5 — Anomaly Detection** | 3+ standard deviations from the mean on numeric fields, optional scatter plot, and an audit view of flagged rows. |
| **User cap removed** | The v1 limit of 5 users is lifted; Admins manage user count directly. |

### 2.3 Unchanged in v2 (Carried Forward from v1)

- All v1 connectors (`FileConnector`, `RestAPIConnector`) and the `BaseConnector` plugin pattern
- Agents not mentioned in v2: `IngestAgent`, `ForecastAgent`, `PatternAgent`, `InsightAgent`, `NotificationAgent`, `OrchestratorAgent`, `RouterAgent`. `ProfileAgent`, `TrendAgent`, and `AnomalyAgent` see behavior changes tied to the card redesign but no fundamental re-architecture.
- Widgets outside the five redesigned cards (forecast chart, insight feed, notification center)
- Role model: Admin and Viewer
- JWT auth
- Tech stack (FastAPI, LangGraph, Celery + Redis, PostgreSQL, React + TypeScript, etc.)
- `docker compose` local dev and `docker-compose.prod.yml` deployability

---

## 3. What We Are NOT Building (v2)

- ❌ Database connectors (PostgreSQL, MySQL) → future
- ❌ Cloud warehouse connectors (Snowflake, BigQuery, Redshift) → future
- ❌ External notifications (email, Slack) → future
- ❌ Password reset / self-service password flows → future
- ❌ Password complexity / strength requirements → future
- ❌ Additional dashboard self-service (rename dashboard, duplicate widgets, multiple dashboards per user) → future
- ❌ OAuth / SSO → future
- ❌ Multi-tenant / org isolation → future
- ❌ Custom agent builder → future
- ❌ Real-time streaming ingestion → future
- ❌ Mobile app → future
- ❌ Redesign of Forecast, Pattern, Insight, and Notification agents/widgets → handled in their own future specs

---

## 4. Feature Specifications

### 4.1 Account Management (New)

**Access.** Admin-only page reached from the header menu ("Account Management"). Viewers do not see the menu entry and receive a 403 if they navigate to the route directly.

**User Model.**

| Field | Notes |
|---|---|
| `email` | Login identifier. Unique across the instance. |
| `password` | Assigned by Admin at creation; stored as a salted hash. No self-service reset in v2. |
| `role` | `Admin` or `Viewer`. |
| `status` | `active` or `disabled`. Disabled users cannot log in but their audit history is preserved. |
| `created_at`, `updated_at`, `created_by`, `updated_by` | Provenance fields for the audit log. |

**Admin Capabilities.**
- Create a user: email, initial password, role.
- Modify a user: change email, role, status, or reset their password to a new Admin-assigned value.
- Delete a user: hard delete permitted; all dashboard layouts owned by that user are also removed.
- Change any other user's role — including promoting a Viewer to Admin or demoting an Admin to Viewer.

**Invariants.**
- At least one active Admin must exist at all times. The system blocks any action (delete, demote, or disable) that would leave zero active Admins, with a clear error message.
- An Admin cannot delete their own account if they are the last Admin. They may delete themselves only if at least one other active Admin exists.
- Email addresses are unique; attempts to create or rename to an existing email are rejected.

**Audit Log.**
- Every create, modify, delete, role change, status change, and password reset is written to an immutable `user_audit_log` table.
- Fields: `timestamp`, `actor_user_id`, `actor_email`, `target_user_id`, `target_email`, `action`, `before_value`, `after_value`, `ip_address`.
- Audit log is viewable only by Admins, on a sub-tab of the Account Management page, with filtering by actor, target, action type, and date range.

**API Endpoints (representative).**
- `GET /api/users` — list (Admin)
- `POST /api/users` — create (Admin)
- `PATCH /api/users/{id}` — modify (Admin)
- `DELETE /api/users/{id}` — delete (Admin)
- `GET /api/users/audit-log` — read audit log (Admin, paginated + filterable)

---

### 4.2 Per-Source Polling Schedule (New)

**Access.** Admins only. Viewers see the resulting refresh cadence but cannot change it.

**Scope.** Schedules are configured **per data source**, not globally. Both `FileConnector` (watched folders) and `RestAPIConnector` support schedules.

**Schedule Options.**
- **Presets:** every 5 minutes, every 15 minutes, every hour, every 6 hours, daily, weekly. Presets cover the common cases and are the recommended default UI.
- **Custom cron expression:** exposed behind an "Advanced" toggle for Admins who need non-standard cadences.
- **Manual "Refresh Now":** a button on each data source card that triggers an immediate poll, independent of the schedule. Available to Admins.

**Execution.**
- Celery Beat (added to the existing Celery + Redis stack) schedules polls and enqueues jobs to the existing Celery workers.
- Each scheduled poll invokes `IngestAgent` → `ProfileAgent` → downstream agents via the existing `OrchestratorAgent`, identical to v1's ingest flow. The only new behavior is the trigger.

**Failure Handling.**
- On poll failure, the system retries up to 3 times with exponential backoff (30s, 2m, 10m).
- After 3 consecutive failed polls (i.e., a full scheduled cycle fails), the data source is marked `degraded` and a notification is sent to all Admins via the existing in-app notification center.
- A source remains in `degraded` state until the next successful poll (scheduled or manual).
- Every poll attempt (success or failure) is recorded in a `source_poll_log` table with timestamp, duration, status, and error message. Admins can view this log from the data source configuration panel.

**Data Source States.**
`active` (polling on schedule), `paused` (schedule disabled, manual refresh only), `degraded` (recent failures), `disconnected` (auth or connection fundamentally broken — requires Admin intervention).

---

### 4.3 Dashboard Enhancements

**Per-user private layout.**
- Each user has their own dashboard layout stored server-side, keyed by `user_id`.
- The layout captures widget positions, sizes, and per-widget settings (e.g., selected column in a card's dropdown).
- Data sources themselves remain shared across users; only the layout and view state are personal.

**Layout persistence.**
- Layout is saved on every change (debounced), not only on logout.
- On login, the user's last saved layout is rendered immediately. First-time users see a default starter layout that they can then modify.
- If a widget's underlying data source has been deleted, the widget renders an empty state with a "remove widget" action rather than erroring.

**Source selector.**
- A dropdown at the top of the Dashboard page lists all data sources the user has access to.
- All source-scoped cards (Cards #1–#5) re-render against the selected source.
- **Persistence.** The user's most recently selected source is stored per-user and restored on the next login, not just within the current session.
- **Deactivated source handling.** If the user's last selected source has been deactivated or deleted by an Admin since their previous session:
  - The dropdown shows the source name struck through (or similarly visually marked) with a "Deactivated" or "Unavailable" badge.
  - Cards #1–#5 render a prominent banner/empty state explaining the source is unavailable and prompting the user to select a different source.
  - Once the user selects an active source, the dropdown reverts to normal and the last-selected value is updated to that new source.
- If no source is connected yet, cards render a clear empty state directing Admins to add a source and Viewers to contact an Admin.

---

### 4.4 Light / Dark Mode

**Scope.** Available to all users regardless of role.

**Toggle location.** A theme toggle control in the header (next to the user menu), available on every page of the app.

**Behavior.**
- Toggling is instantaneous — no page reload required.
- The selected theme is the user's personal preference and persists across sessions (stored server-side against the user record).
- On first login, the default theme is **light mode**. Users may optionally have the app follow the operating system's preference; if so, OS preference is used until the user makes an explicit choice, at which point the explicit choice wins.

**Coverage.**
- All pages, panels, and modals must render correctly in both themes: Dashboard, Account Management, data source management panel, agent activity log, notification center.
- All five cards (Data Profile, Profile Details, Descriptive Statistics, Trend Analysis, Anomaly Detection) and their visualizations (bell curve, trend line, scatter plot) must render correctly in both themes, with chart colors chosen for sufficient contrast against each background.

**Data model.**
- `users` table gains a `theme_preference` field with allowed values `light`, `dark`, `system`.

---

### 4.5 Card Specifications

The five redesigned cards all operate on the data source currently selected in the top-of-page dropdown.

#### Column Classification (applies to Cards #1–#5)

`ProfileAgent` now emits a classification for each column alongside its existing metadata:

- **Categorical:** cannot be aggregated or measured as a continuum. Strings, enums, booleans.
- **Discrete:** can be aggregated but does not represent a continuum. Integer counts, ordinal codes.
- **Continuous:** can be aggregated and represents a continuum. Floats, dates, timestamps, durations.

**"Numeric" throughout the card specs means discrete + continuous** (i.e., any field that can be aggregated). Categorical fields are excluded from statistics, trend, and anomaly cards.

#### Card #1 — Data Profile (summary)

Purpose: at-a-glance shape of the dataset.

Displays:
- **Title:** "Data Profile"
- **Number of Rows** — total row count
- **Number of Columns** — total column count
- **Number of Categorical Columns**
- **Number of Discrete Columns**
- **Number of Continuous Columns**

No interaction beyond auto-refresh when the underlying source is re-polled.

#### Card #2 — Profile Details (table)

Purpose: per-column breakdown of the dataset.

One row per column in the source, with the following fields:

| Field | Notes |
|---|---|
| `column` | Column name |
| `data_type` | Inferred type (string, int, float, datetime, bool, etc.) |
| `null_rate` | Percentage of null values (0–100%) |
| `cardinality` | Count of distinct non-null values |
| `pk_candidate` | Boolean. `true` when the column is 100% unique AND 100% non-null. |
| `data_classification` | `categorical` / `discrete` / `continuous` |

Table supports sorting and search/filter by column name.

#### Card #3 — Descriptive Statistics

Purpose: summary statistics and distribution for a selected numeric column.

- **Column dropdown:** lists all numeric columns (discrete + continuous). Defaults to the first discrete column; falls back to the first continuous column if none are discrete.
- **Stats shown:** `min`, `max`, `std`, `mean`, `mode`.
- **Distribution:** bell curve / density plot of the selected column, with the computed stats called out on the chart (annotated lines or markers at mean, ±1σ, ±2σ, ±3σ).
- Categorical columns are excluded.

#### Card #4 — Trend Analysis

Purpose: visualize how a numeric field moves over time.

- **Column dropdown:** numeric columns (discrete + continuous). Defaults to the first discrete column; falls back to the first continuous column.
- **X-axis:** date/time field. If the source has multiple date columns, a secondary dropdown lets the user pick which one; otherwise the sole date column is used.
- **Y-axis:** the selected numeric field.
- **Behavior:** line chart with appropriate time aggregation (auto-selected based on date range: hourly / daily / weekly / monthly).
- If the source has no date/time column, the card renders an empty state explaining why trend analysis is unavailable.

#### Card #5 — Anomaly Detection

Purpose: surface outlier data points in a numeric field.

- **Column dropdown:** numeric columns only (discrete + continuous).
- **Detection rule:** values more than **3 standard deviations from the mean** are flagged as anomalies. (v1's Isolation Forest logic in `AnomalyAgent` is retained for other agents/widgets; this card uses the simple z-score rule for transparency to users.)
- **Visualization toggle:** default view (summary count + list) and optional scatter plot view showing all points with anomalies highlighted.
- **Audit view:** clicking "Audit" opens a panel listing the flagged rows. For each flagged row, the panel shows the full row contents and highlights which field(s) triggered the flag.
- **v2 audit scope:** read-only view of flagged rows and fields. Actions like "mark false positive," export, and commenting are deferred to a future version.

---

## 5. Data Model Additions

New or modified tables (Postgres):

| Table | Purpose |
|---|---|
| `users` | Modified — add `status`, `created_by`, `updated_by`, `password_updated_at`, `theme_preference`, `last_selected_source_id`. |
| `user_audit_log` | New — immutable record of all user management actions. |
| `user_dashboard_layouts` | New — per-user serialized layout + widget state. |
| `source_schedules` | New — per-source schedule config (preset or cron) and `enabled` flag. |
| `source_poll_log` | New — history of poll attempts with status, duration, error. |
| `column_profiles` | Modified — add `data_classification` and `pk_candidate` columns. |

---

## 6. Architecture Changes

The v1 architecture is preserved. v2 adds:

- **Celery Beat** alongside the existing Celery workers, to drive scheduled polls from `source_schedules`.
- **Account Management** routes and middleware in FastAPI, with Admin-role enforcement.
- **Dashboard Layout** endpoints in FastAPI (`GET/PUT /api/dashboard/layout`).
- **Audit Log** write path hooked into every user management endpoint.

No change to the LangGraph agent network topology. `ProfileAgent` is extended to emit `data_classification` and `pk_candidate`. `AnomalyAgent` gains a z-score output path in addition to its v1 Isolation Forest logic.

---

## 7. Connector Plugin Pattern (Unchanged)

The `BaseConnector` interface from v1 is untouched. Schedule configuration is layered on top of it (stored in `source_schedules`) and does not require connector authors to change their implementations.

---

## 8. Acceptance Criteria (v2 Complete When...)

### Account Management
- [ ] An Admin can create a user with email, initial password, and role from the Account Management page.
- [ ] An Admin can modify any user's email, role, status, and password.
- [ ] An Admin can delete any user, with the exception that the system prevents any action that would leave zero active Admins.
- [ ] Viewers cannot access the Account Management page or its API routes.
- [ ] Every user management action is recorded in the audit log with actor, target, action, before/after values, and timestamp.
- [ ] The audit log is viewable and filterable only by Admins.

### Polling Schedules
- [ ] An Admin can set a schedule (preset or cron) per data source.
- [ ] A scheduled poll triggers `IngestAgent` and downstream agents identically to a manual ingest.
- [ ] "Refresh Now" immediately polls the source regardless of schedule.
- [ ] A source that fails 3 consecutive scheduled polls is marked `degraded` and all Admins are notified in-app.
- [ ] Every poll attempt is recorded in `source_poll_log`.

### Dashboard
- [ ] Each user's dashboard layout persists across sessions and is private to them.
- [ ] Changing the source dropdown re-renders Cards #1–#5 against the selected source.
- [ ] A first-time user sees a default starter layout.
- [ ] Widgets whose source was deleted render an empty state, not an error.
- [ ] The user's last-selected source is restored on next login if it is still active.
- [ ] If the last-selected source has been deactivated, it is visually marked in the dropdown and cards prompt the user to select another source.

### Theme
- [ ] A user can toggle between light and dark mode from the header on any page.
- [ ] The theme change is instantaneous and requires no page reload.
- [ ] The selected theme persists across sessions, per user.
- [ ] All pages, modals, and card visualizations render correctly in both themes.

### Cards
- [ ] Card #1 correctly reports rows, columns, and the three classification counts for the selected source.
- [ ] Card #2 lists every column with type, null rate, cardinality, PK-candidate flag, and classification.
- [ ] Card #3 defaults to the first discrete column, offers all numeric columns in the dropdown, and renders a bell curve with min/max/std/mean/mode called out.
- [ ] Card #4 defaults to the first discrete column, plots it against a date axis, and gracefully handles sources with no date column.
- [ ] Card #5 flags values > 3σ from the mean, offers a scatter plot toggle, and provides an audit panel showing flagged rows and triggering fields.

### Non-functional
- [ ] The 5-user cap from v1 is removed; at least 20 users can coexist without degradation.
- [ ] All new endpoints enforce Admin-only access where specified.
- [ ] The app continues to run end-to-end with `docker compose up`, now including Celery Beat.

---

## 9. Future Version Placeholders (Deferred from v2)

Carried forward from v1 and still out of scope:

- **Database connectors** (PostgreSQL, MySQL)
- **Cloud warehouse connectors** (Snowflake, BigQuery, Redshift)
- **External notifications** (email, Slack)
- **Custom agent builder**
- **Multi-tenant / org isolation**
- **Real-time streaming ingestion**
- **Mobile app**

New placeholders introduced by v2:

- **Password reset / self-service auth flows**
- **Password complexity / strength requirements**
- **OAuth / SSO**
- **Additional dashboard self-service** (rename dashboard, duplicate widgets, multiple dashboards per user)
- **Redesigns of Forecast, Pattern, Insight, and Notification agents + widgets** (each will ship with its own spec)
- **Richer anomaly audit** (mark false positive, comment, export)
- **Confidence intervals and alternative distribution views on Card #3**
