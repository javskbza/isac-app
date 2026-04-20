# Data Intelligence Platform v1

An autonomous, agent-powered data intelligence platform that connects to data sources, learns from their patterns over time, and proactively surfaces insights — anomalies, forecasts, trends, and next-best-actions — via a real-time dashboard.

## Quick Start

```bash
cp platform/.env.example platform/.env
# Edit platform/.env with your settings
cd platform
docker compose up
```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | React dashboard UI |
| Backend API | http://localhost:8000 | FastAPI REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Cache & task queue |

## Environment Setup

1. Copy the example env file: `cp platform/.env.example platform/.env`
2. Update `JWT_SECRET` to a strong random value
3. Change `POSTGRES_PASSWORD` to a secure password
4. Set `VITE_API_URL` if your backend runs on a different host

## Architecture

- **Backend**: FastAPI + LangGraph agent network + Celery task queue
- **Frontend**: React 18 + TypeScript + shadcn/ui + react-grid-layout
- **Database**: PostgreSQL (metadata, insights, profiles)
- **Cache/Queue**: Redis + Celery

See `platform/` for full source code and detailed docs.
