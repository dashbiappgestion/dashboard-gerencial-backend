import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import get_settings
from app.database import reset_engine, test_connection
from app.routers import kpis, forecast

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_engine()
    result = test_connection()
    if result["ok"]:
        logger.info(
            "Supabase conectado %s:%s user=%s regions=%s",
            result["host"],
            result["port"],
            result["user"],
            result["regions"],
        )
    else:
        logger.error(
            "Supabase desconectado %s:%s error=%s",
            result["host"],
            result["port"],
            result["error"],
        )
    yield
    reset_engine()


app = FastAPI(
    title="Dashboard Gerencial API",
    description="API del Balanced Scorecard - Apple Inc.",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kpis.router)
app.include_router(forecast.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    return {"status": "ok", "message": "Dashboard Gerencial API - Backend Activo"}

@app.get("/dashboard")
def dashboard_page():
    return {"status": "ok", "message": "Endpoint reemplazado por Angular frontend"}

@app.post("/api/wakeup")
def wakeup_server(x_cron_secret: str | None = Header(None, alias="X-Cron-Secret")):
    expected_secret = os.getenv("CRON_SECRET", "")
    if not x_cron_secret or x_cron_secret != expected_secret:
        raise HTTPException(status_code=401, detail="No autorizado")
    return {"status": "ok", "message": "Render Online"}
