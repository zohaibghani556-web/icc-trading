"""
main.py — Application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.database import create_tables
from app.api.v1 import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await create_tables()
        print("✅ Database tables ready")
    except Exception as e:
        print(f"⚠️ Database not available: {e}")
        print("⚠️ Running without database — ICC engine still works")
    print(f"✅ ICC Trading Assistant running in {settings.ENVIRONMENT} mode")
    yield
    print("👋 Server shutting down")


app = FastAPI(
    title="ICC Trading Assistant",
    description="Decision-support platform for ICC futures trading",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
async def health_check():
    return {
        "status": "online",
        "service": "ICC Trading Assistant",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }
