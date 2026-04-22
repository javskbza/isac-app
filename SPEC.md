# SPEC.md — Data Intelligence Platform (v1)

---

## 1. Vision

An autonomous, agent-powered data intelligence platform that connects to data sources, learns from their patterns over time, and proactively surfaces insights — anomalies, forecasts, trends, and next-best-actions — to users via a real-time dashboard with customizable widgets and in-app notifications. The platform is modular by design, built to grow from files and APIs (v1) to databases (v2) and cloud warehouses (v3).

---

## 2. What We ARE Building (v1)

### Data Connectivity
- File ingestion: CSV, Excel (.xlsx), JSON (upload or watched folder)
- API connectors: REST APIs via a configurable connector plugin (URL, auth headers, polling interval)
- Metadata retrieval: column names, types, row counts, null rates, cardinality
- Schema inference: automatic type detection, relationship hints between datasets

### Agent Network

| Agent | Responsibility |
|---|---|
| `IngestAgent` | Pulls data from files/APIs, normalizes to internal format |
| `ProfileAgent` | Computes statistics: nulls, distributions, min/max, cardinality |
| `TrendAgent` | Detects directional trends over time in numeric fields |
| `ForecastAgent` | Produces short-horizon forecasts using time-series modeling |
| `AnomalyAgent` | Flags statistical outliers and unexpected shifts |
| `PatternAgent` | Identifies recurring patterns, seasonality, correlations |
| `InsightAgent` | Synthesizes findings into human-readable intelligence cards |
| `OrchestratorAgent` | Coordinates agent execution order, manages dependencies |
| `RouterAgent` | Routes messages between agents, handles retries and failures |
| `NotificationAgent` | Creates in-app notifications from surfaced insights |

### Dashboard UI
- Customizable widget grid (drag-and-drop)
- Widget types: KPI card, trend line, anomaly alert, forecast chart, data profile summary, insight feed
- Notification center (in-app bell icon with unread count)
- Data source management panel (add/remove/configure sources)
- Agent activity log (what each agent has processed and when)

### Multi-user
- Up to 5 users per instance
- Shared data sources and dashboards
- Per-user notification preferences (which insight types to receive)
- Simple role model: Admin and Viewer

---

## 3. What We Are NOT Building (v1)

- ❌ Database connectors (PostgreSQL, MySQL) → v2
- ❌ Cloud warehouse connectors (Snowflake, BigQuery) → v3
- ❌ External notifications (email, Slack) → v2
- ❌ Multi-tenant / org isolation → future version
- ❌ Custom agent builder (users adding their own agents) → future
- ❌ Real-time streaming ingestion (polling only in v1)
- ❌ Mobile app

---

## 4. Recommended Tech Stack

### Backend — Python

| Layer | Technology | Reason |
|---|---|---|
| API server | **FastAPI** | Async, fast, great for agent communication and REST endpoints |
| Agent orchestration | **LangGraph** | Native support for multi-agent graphs, state machines, and agent-to-agent routing |
| Data profiling | **ydata-profiling** + **pandas** | Industry standard for automated data profiling |
| Forecasting | **Prophet** (Meta) + **statsmodels** | Robust time-series, handles seasonality automatically |
| Anomaly detection | **scikit-learn** (Isolation Forest) | Lightweight, no GPU required |
| Task queue | **Celery** + **Redis** | Async agent job execution, retry logic, scheduling |
| Metadata & state store | **PostgreSQL** | Stores source configs, agent outputs, profiles, insight history |
| File parsing | **pandas**, **openpyxl**, **json** | Native support for CSV, Excel, JSON |

### Frontend — React + TypeScript

| Layer | Technology | Reason |
|---|---|---|
| Framework | **React 18 + TypeScript** | Type safety, large ecosystem |
| UI components | **shadcn/ui** | Clean, accessible, composable |
| Charts | **Recharts** | Lightweight, React-native charting |
| Dashboard grid | **react-grid-layout** | Drag-and-drop widget positioning |
| State management | **Zustand** | Lightweight, no Redux boilerplate |
| API client | **TanStack Query** | Async data fetching with caching |

### Infrastructure

| Layer | Technology |
|---|---|
| Local dev | **Docker Compose** (all services containerized) |
| Cloud-ready | **Docker + docker-compose.prod.yml** (deployable to AWS ECS, Railway, Fly.io) |
| Auth | **JWT** (simple token auth, no OAuth in v1) |

---

## 5. Architecture Overview

```
┌─────────────────────────────────────────┐
│              React Frontend             │
│   Dashboard | Widgets | Notifications   │
└───────────────────┬─────────────────────┘
                    │ REST / WebSocket
┌───────────────────▼─────────────────────┐
│           FastAPI Backend               │
│   Auth | Source Mgmt | Insight API      │
└──────┬──────────────────────┬───────────┘
       │                      │
┌──────▼──────┐      ┌────────▼────────┐
│   Celery    │      │   PostgreSQL    │
│ Task Queue  │      │  Metadata +     │
│  (Redis)    │      │  Insight Store  │
└──────┬──────┘      └─────────────────┘
       │
┌──────▼───────────────────────────────┐
│          LangGraph Agent Network      │
│                                      │
│  Orchestrator → Router               │
│       ↓              ↓               │
│  IngestAgent    NotificationAgent    │
│  ProfileAgent                        │
│  TrendAgent                          │
│  ForecastAgent                       │
│  AnomalyAgent                        │
│  PatternAgent                        │
│  InsightAgent                        │
└──────────────────────────────────────┘
```

---

## 6. Connector Plugin Pattern

Each data source type is a **plugin** implementing a standard interface:

```python
class BaseConnector:
    def connect(self, config: dict) -> bool
    def get_metadata(self) -> SourceMetadata
    def fetch_data(self) -> pd.DataFrame
    def get_schema(self) -> Schema
```

v1 ships with `FileConnector` and `RestAPIConnector`. New connectors (Postgres, Snowflake) are added by implementing this interface — no core changes required.

---

## 7. Acceptance Criteria (v1 Complete When...)

- [ ] A user can upload a CSV/Excel/JSON file and the system automatically profiles it within 60 seconds
- [ ] A user can configure a REST API connector (URL + auth) and the system polls it on a defined schedule
- [ ] All 10 agents execute in correct dependency order via the Orchestrator
- [ ] Anomalies, trends, and forecasts appear as widgets on the dashboard
- [ ] The InsightAgent produces at least one human-readable insight card per data source
- [ ] In-app notifications appear when a new anomaly or forecast is generated
- [ ] Up to 5 users can log in with separate accounts sharing the same data sources
- [ ] Admins can add/remove data sources; Viewers can only view dashboards
- [ ] The app runs end-to-end with `docker compose up`
- [ ] A `docker-compose.prod.yml` exists for cloud deployment

---

## 8. v2 / v3 Placeholders (Out of Scope Now, Designed For)

- **v2**: PostgreSQL + MySQL connectors, Email + Slack notifications, larger user base support
- **v3**: Snowflake, BigQuery, Redshift connectors
- **Future**: Custom agent builder, mobile app, multi-tenant org isolation, streaming ingestion
