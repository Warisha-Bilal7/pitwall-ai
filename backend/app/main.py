from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 PITWALL·AI starting up...")
    try:
        await init_db()
    except Exception as e:
        print(f"⚠️  Database not available yet: {e}")
        print("   Start Docker and run again to initialise tables.")
    yield
    print("🛑 PITWALL·AI shutting down...")

app = FastAPI(
    title="PITWALL·AI",
    description="F1 Race Intelligence Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # Vite dev server (Phase 5)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "project": "PITWALL·AI"}


@app.get("/")
async def root():
    return {"message": "Welcome to PITWALL·AI — F1 Race Intelligence Platform"}