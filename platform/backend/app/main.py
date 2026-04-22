from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, auth, sources, profiles, insights, notifications, agent_logs, users, dashboard
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load all enabled source schedules into Celery Beat on startup
    try:
        from app.beat_scheduler import load_all_schedules
        import asyncio
        await asyncio.get_event_loop().run_in_executor(None, load_all_schedules)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to load beat schedules at startup")
    yield


app = FastAPI(
    title="Data Intelligence Platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/auth")
app.include_router(sources.router)
app.include_router(profiles.router)
app.include_router(insights.router)
app.include_router(notifications.router)
app.include_router(agent_logs.router)
app.include_router(users.router, prefix="/api")
app.include_router(dashboard.router)
