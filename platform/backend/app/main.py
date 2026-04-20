from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, auth, sources, profiles, insights, notifications, agent_logs
from app.config import settings

app = FastAPI(
    title="Data Intelligence Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
