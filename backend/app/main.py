"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, auth, audit, automation, impact, patches, repositories, skills
from app.core.config import settings
from app.core.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="JDK version upgrade impact analyzer with multi-LLM support",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(repositories.router, prefix="/api/repositories", tags=["Repositories"])
app.include_router(patches.router, prefix="/api/patches", tags=["Patches"])
app.include_router(impact.router, prefix="/api/impact", tags=["Impact Analysis"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
app.include_router(automation.router, prefix="/api/automation", tags=["Automation"])
app.include_router(skills.router, prefix="/api/skills", tags=["Skills"])


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/llm-providers")
async def get_llm_providers() -> dict[str, list[str]]:
    """Get available LLM providers."""
    return {"providers": settings.available_llm_providers}
