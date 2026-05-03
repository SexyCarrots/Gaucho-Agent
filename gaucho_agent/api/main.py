"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from gaucho_agent.api.routes_chat import router as chat_router
from gaucho_agent.api.routes_status import router as status_router
from gaucho_agent.api.routes_sync import router as sync_router
from gaucho_agent.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db()
    yield


app = FastAPI(
    title="Gaucho-Agent API",
    description="Local-first academic assistant for UCSB students.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(sync_router)
app.include_router(status_router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {"message": "Gaucho-Agent API is running.", "docs": "/docs"}
