# TASKS.md — Data Intelligence Platform (v1)

---

## How to Execute

Each task below is handled by a dedicated subagent. Paste the **Kickoff Prompt** at the bottom of this document into your Claude Code terminal to begin. Claude will orchestrate the waves automatically.

---

## Wave 1 — Foundation (Parallel, no dependencies)

### TASK-001 — Project Scaffolding & Docker Setup
**Agent:** SubAgent-Scaffold
**Deliverable:** Monorepo structure, `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example`, root `README.md`
**Structure:**
```
/platform
  /backend
  /frontend
  /infra
  docker-compose.yml
  docker-compose.prod.yml
  .env.example
  README.md
```
**Commit message:** `feat: project scaffolding and docker compose setup`

---

### TASK-002 — Backend Skeleton (FastAPI)
**Agent:** SubAgent-Backend
**Deliverable:** FastAPI app with health check endpoint, JWT auth middleware, CORS config, folder structure (`/routers`, `/models`, `/services`, `/agents`, `/connectors`)
**Commit message:** `feat: fastapi backend skeleton with auth and routing`

---

### TASK-003 — Frontend Skeleton (React + TypeScript)
**Agent:** SubAgent-Frontend
**Deliverable:** Vite + React 18 + TypeScript app, shadcn/ui installed, TanStack Query configured, Zustand store initialized, basic routing (Login, Dashboard, Sources pages)
**Commit message:** `feat: react frontend skeleton with routing and state`

---

### TASK-004 — Database Schema & Migrations
**Agent:** SubAgent-DB
**Deliverable:** PostgreSQL schema via Alembic migrations — tables for `users`, `roles`, `data_sources`, `schemas`, `profiles`, `insights`, `notifications`, `agent_logs`
**Commit message:** `feat: postgresql schema and alembic migrations`

---

### TASK-005 — Connector Plugin Interface
**Agent:** SubAgent-Connectors
**Deliverable:** `BaseConnector` abstract class, `FileConnector` (CSV/Excel/JSON), `RestAPIConnector` (configurable URL + auth headers + polling interval), connector registry
**Commit message:** `feat: connector plugin interface with file and api connectors`

---

## Wave 2 — Agent Network (Depends on TASK-002, TASK-004, TASK-005)

### TASK-006 — LangGraph Agent Graph Setup
**Agent:** SubAgent-AgentGraph
**Deliverable:** LangGraph graph definition wiring all 10 agents, `OrchestratorAgent` managing execution order, `RouterAgent` handling inter-agent message passing and retries
**Commit message:** `feat: langgraph agent network with orchestrator and router`

---

### TASK-007 — IngestAgent + ProfileAgent
**Agent:** SubAgent-Ingest
**Deliverable:** `IngestAgent` fetches and normalizes data from connectors into pandas DataFrames; `ProfileAgent` computes nulls, distributions, min/max, cardinality, row counts using ydata-profiling; outputs stored to DB
**Commit message:** `feat: ingest and profile agents`

---

### TASK-008 — TrendAgent + ForecastAgent
**Agent:** SubAgent-Analytics
**Deliverable:** `TrendAgent` detects directional trends in numeric time-series fields; `ForecastAgent` generates short-horizon forecasts using Prophet; results stored as insight records
**Commit message:** `feat: trend and forecast agents`

---

### TASK-009 — AnomalyAgent + PatternAgent
**Agent:** SubAgent-Detection
**Deliverable:** `AnomalyAgent` uses Isolation Forest to flag outliers; `PatternAgent` identifies seasonality, recurring patterns, and correlations between fields; results stored as insight records
**Commit message:** `feat: anomaly and pattern agents`

---

### TASK-010 — InsightAgent + NotificationAgent
**Agent:** SubAgent-Insight
**Deliverable:** `InsightAgent` synthesizes agent outputs into human-readable insight cards (min 1 per source); `NotificationAgent` creates in-app notification records for anomalies and forecasts
**Commit message:** `feat: insight and notification agents`

---

## Wave 3 — API Layer (Depends on Wave 2)

### TASK-011 — REST API Endpoints
**Agent:** SubAgent-API
**Deliverable:** Full FastAPI router coverage:
- `POST /sources` — add data source
- `GET /sources` — list sources
- `DELETE /sources/{id}` — remove source
- `GET /profiles/{source_id}` — fetch profile
- `GET /insights/{source_id}` — fetch insights
- `GET /notifications` — fetch user notifications
- `PATCH /notifications/{id}/read` — mark read
- `GET /agents/log` — agent activity log
- `POST /auth/login` + `POST /auth/register`
**Commit message:** `feat: full rest api endpoint coverage`

---

## Wave 4 — Frontend Features (Depends on TASK-003, TASK-011)

### TASK-012 — Auth Flow (Login + Register UI)
**Agent:** SubAgent-Auth-UI
**Deliverable:** Login and Register pages wired to JWT API, token stored in memory (not localStorage), redirect on success
**Commit message:** `feat: auth ui with login and register`

---

### TASK-013 — Data Source Management UI
**Agent:** SubAgent-Sources-UI
**Deliverable:** Sources page — add file upload (drag-and-drop), configure REST API connector form, list connected sources with status badges, delete source action
**Commit message:** `feat: data source management ui`

---

### TASK-014 — Dashboard Widget Grid
**Agent:** SubAgent-Dashboard-UI
**Deliverable:** Drag-and-drop dashboard using react-grid-layout; widget types: KPI card, trend line chart (Recharts), anomaly alert card, forecast chart, data profile summary, insight feed; widgets load data from API via TanStack Query
**Commit message:** `feat: customizable dashboard widget grid`

---

### TASK-015 — Notification Center UI
**Agent:** SubAgent-Notifications-UI
**Deliverable:** Bell icon in navbar with unread count badge; slide-out notification panel listing insight notifications with type icons; mark-as-read on click; real-time count refresh via polling
**Commit message:** `feat: in-app notification center`

---

### TASK-016 — Agent Activity Log UI
**Agent:** SubAgent-AgentLog-UI
**Deliverable:** Agent log page showing per-agent execution history — source name, agent name, status (success/error), timestamp, output summary
**Commit message:** `feat: agent activity log ui`

---

## Wave 5 — Integration & Polish (Depends on all prior waves)

### TASK-017 — End-to-End Integration Test
**Agent:** SubAgent-Integration
**Deliverable:** Upload a sample CSV → verify full agent pipeline runs → verify insight card and notification appear in UI → verify all acceptance criteria from SPEC.md are met → document any gaps
**Commit message:** `test: end-to-end integration validation`

---

### TASK-018 — README & Deployment Guide
**Agent:** SubAgent-Docs
**Deliverable:** Complete `README.md` with local setup instructions (`docker compose up`), env var reference, how to add a new connector, how to add a new agent, cloud deployment guide for AWS ECS / Fly.io
**Commit message:** `docs: readme and deployment guide`

---

## Kickoff Prompt — Paste This Into Claude Code

```
Read SPEC.md and TASKS.md in full before doing anything.

You are the orchestrator for a spec-driven development project.
Your job is to implement all tasks in TASKS.md using the Task tool,
one subagent per task, following the wave order defined in the file.

Rules:
- Do not write any code yourself. Delegate every task to a subagent.
- Wave 1 tasks (TASK-001 through TASK-005) run in parallel.
- Wave 2 tasks begin only after all Wave 1 tasks are complete.
- Continue wave-by-wave through Wave 5.
- After each task completes, the subagent must commit with the exact
  commit message specified in TASKS.md before the next task begins.
- If a task fails, log the error and continue with tasks that don't
  depend on the failed one. Flag failures at the end.
- When all tasks are complete, print a summary: tasks completed,
  tasks failed, and whether all SPEC.md acceptance criteria are met.

Begin now with Wave 1.
```

---

## Quick Reference — Wave Dependency Map

```
Wave 1 (parallel):   001  002  003  004  005
                          ↓         ↓    ↓
Wave 2 (parallel):       006  007  008  009  010
                                    ↓
Wave 3:                            011
                          ↓              ↓
Wave 4 (parallel):       012  013  014  015  016
                                    ↓
Wave 5 (parallel):                 017  018
```
