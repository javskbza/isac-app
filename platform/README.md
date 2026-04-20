# Data Intelligence Platform v1

An autonomous, agent-powered data intelligence platform that connects to data sources, learns from their patterns over time, and proactively surfaces insights — anomalies, forecasts, trends, and next-best-actions — via a real-time dashboard with customizable widgets and in-app notifications.

---

## Local Setup (docker compose up)

### Prerequisites
- Docker Desktop 4.x+ (or Docker Engine + Compose plugin)
- 4 GB RAM minimum

### Steps

```bash
# 1. Clone the repo and enter the platform directory
cd platform

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env — at minimum change JWT_SECRET and POSTGRES_PASSWORD

# 3. Start all services
docker compose up --build

# 4. Run database migrations (first time only)
docker compose exec backend alembic upgrade head

# 5. Open the app
open http://localhost:3000
```

### Services at a glance

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:3000 | React dashboard |
| Backend API | http://localhost:8000 | FastAPI |
| API Docs | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | Exposed for local dev |
| Redis | localhost:6379 | Task queue broker |

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `platform` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password — **change in production** |
| `POSTGRES_DB` | `platform_db` | Database name |
| `DATABASE_URL` | see .env.example | Full async SQLAlchemy URL |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `JWT_SECRET` | _(required)_ | Secret key for signing JWTs — **must be random in production** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `60` | Token expiry in minutes |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `DEBUG` | `true` | Enables SQLAlchemy query logging |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL seen by the browser |

---

## How to Add a New Connector

The connector system uses a plugin pattern. All connectors implement `BaseConnector`.

### 1. Create a new connector class

```python
# platform/backend/app/connectors/my_connector.py
from app.connectors.base import BaseConnector, SourceMetadata, SourceSchema
import pandas as pd

class MyConnector(BaseConnector):
    def connect(self, config: dict) -> bool:
        # Establish connection
        self._connected = True
        return True

    def fetch_data(self) -> pd.DataFrame:
        # Return data as DataFrame
        return pd.DataFrame(...)

    def get_metadata(self) -> SourceMetadata:
        return SourceMetadata(name="...", source_type="my_type", ...)

    def get_schema(self) -> SourceSchema:
        return SourceSchema(columns=[...], row_count=..., inferred_at=...)
```

### 2. Register it

```python
# In app/connectors/registry.py, add to _register_defaults():
from app.connectors.my_connector import MyConnector
ConnectorRegistry.register("my_type", MyConnector)
```

### 3. Add a migration (if storing new config fields)

```bash
alembic revision --autogenerate -m "add my_type connector support"
alembic upgrade head
```

That's it. No core changes required.

---

## How to Add a New Agent

Agents are Python functions with the signature `(state: AgentState) -> AgentState`.

### 1. Create the agent

```python
# platform/backend/app/agents/my_agent.py
from app.agents.state import AgentState
from datetime import datetime, timezone

def my_agent(state: AgentState) -> AgentState:
    logs = list(state.get("logs", []))
    # ... do work ...
    logs.append({
        "agent_name": "MyAgent",
        "status": "success",
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "completed_at": datetime.now(tz=timezone.utc).isoformat(),
        "output_summary": "Did something useful",
    })
    return {**state, "my_output": {...}, "logs": logs}
```

### 2. Wire it into the graph

```python
# In platform/backend/app/agents/orchestrator.py
from app.agents.my_agent import my_agent

# In build_agent_graph():
graph.add_node("my_agent", my_agent)
graph.add_edge("pattern", "my_agent")   # insert at right position
graph.add_edge("my_agent", "insight")
```

---

## Cloud Deployment

### Using docker-compose.prod.yml

```bash
# 1. Build and push images
docker build -t your-registry.com/backend:latest ./backend
docker build -t your-registry.com/frontend:latest ./frontend
docker push your-registry.com/backend:latest
docker push your-registry.com/frontend:latest

# 2. Set environment variables on the server
export REGISTRY=your-registry.com
export TAG=latest
export JWT_SECRET=$(openssl rand -hex 32)
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
# ... set all other required vars ...

# 3. Deploy
docker compose -f docker-compose.prod.yml up -d

# 4. Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### AWS ECS (Fargate)

1. Push images to ECR:
   ```bash
   aws ecr create-repository --repository-name platform/backend
   aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
   docker tag your-registry.com/backend:latest <account>.dkr.ecr.<region>.amazonaws.com/platform/backend:latest
   docker push <account>.dkr.ecr.<region>.amazonaws.com/platform/backend:latest
   ```

2. Create an ECS cluster, task definitions for `backend`, `frontend`, `celery_worker`.

3. Use RDS PostgreSQL and ElastiCache Redis instead of containerized DB/Redis.

4. Set environment variables via ECS task definition or AWS Secrets Manager.

5. Put an Application Load Balancer in front of the `frontend` (port 80) and `backend` (port 8000) services.

### Fly.io

```bash
# Install flyctl and login
brew install flyctl && fly auth login

# Launch each service
cd backend && fly launch --name platform-backend
cd ../frontend && fly launch --name platform-frontend

# Set secrets
fly secrets set JWT_SECRET=... DATABASE_URL=... REDIS_URL=... -a platform-backend

# Deploy
fly deploy -a platform-backend
fly deploy -a platform-frontend
```

---

## Running Tests

```bash
cd platform/backend
pip install -r requirements.txt pytest pytest-asyncio
pytest tests/ -v
```

---

## Architecture Overview

```
React Frontend (port 3000)
    ↓ REST API
FastAPI Backend (port 8000)
    ↓                  ↓
Celery + Redis    PostgreSQL
(Task Queue)     (Metadata Store)
    ↓
LangGraph Agent Pipeline:
  IngestAgent → ProfileAgent → TrendAgent → ForecastAgent
  → AnomalyAgent → PatternAgent → InsightAgent → NotificationAgent
```

---

## v2 / v3 Roadmap

- **v2**: PostgreSQL + MySQL connectors, Email + Slack notifications
- **v3**: Snowflake, BigQuery, Redshift connectors
- **Future**: Custom agent builder, mobile app, streaming ingestion
