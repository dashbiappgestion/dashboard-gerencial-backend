from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, test_connection
from app.services import kpi_service

router = APIRouter(prefix="/api", tags=["kpis"])


def _db_guard(db: Session):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
    except SQLAlchemyError as exc:
        settings = get_settings()
        detail = (
            f"No se pudo conectar a Supabase ({settings.db_host}:{settings.db_port}). "
            f"Usuario: {settings.db_user}. "
            f"Error: {exc.__cause__ or exc}. "
            "Revisa .env y reinicia: uvicorn app.main:app --reload"
        )
        raise HTTPException(status_code=503, detail=detail) from exc


@router.get("/health")
def health():
    result = test_connection()
    if result["ok"]:
        return {
            "status": "ok",
            "database": "connected",
            "host": result["host"],
            "regions": result["regions"],
        }
    return {
        "status": "ok",
        "database": "disconnected",
        "host": result["host"],
        "port": result["port"],
        "user": result["user"],
        "error": result["error"],
    }


@router.get("/dashboard")
def dashboard(
    anio_inicio: int | None = Query(None, description="Año de inicio del rango"),
    anio_fin: int | None = Query(None, description="Año de fin del rango"),
    db: Session = Depends(get_db),
):
    _db_guard(db)
    return {
        "tarjetas": kpi_service.get_tarjetas(db, anio_inicio, anio_fin),
        "desarrollo": kpi_service.get_desarrollo_categoria(db, anio_inicio, anio_fin),
        "capacitacion_errores": kpi_service.get_capacitacion_errores(db, anio_inicio, anio_fin),
        "satisfaccion": kpi_service.get_satisfaccion(db, None, anio_inicio, anio_fin),
    }


@router.get("/kpis/tarjetas")
def tarjetas(db: Session = Depends(get_db)):
    return kpi_service.get_tarjetas(db)


@router.get("/kpis/desarrollo")
def desarrollo(db: Session = Depends(get_db)):
    return kpi_service.get_desarrollo_categoria(db)


@router.get("/kpis/capacitacion-errores")
def capacitacion_errores(db: Session = Depends(get_db)):
    return kpi_service.get_capacitacion_errores(db)


@router.get("/kpis/satisfaccion")
def satisfaccion(
    region: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return kpi_service.get_satisfaccion(db, region)


@router.get("/regiones")
def regiones(db: Session = Depends(get_db)):
    return kpi_service.get_regiones(db)


@router.get("/kpis/margen-neto/historico")
def margen_historico(
    region: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return kpi_service.get_margen_historico(db, region)


@router.get("/kpis/roi/historico")
def roi_historico(db: Session = Depends(get_db)):
    return kpi_service.get_roi_historico(db)


@router.get("/kpis/nps/historico")
def nps_historico(
    region: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return kpi_service.get_nps_historico(db, region)


@router.get("/kpis/paises/historico")
def paises_historico(db: Session = Depends(get_db)):
    return kpi_service.get_paises_historico(db)


@router.get("/kpis/desarrollo/{categoria}")
def desarrollo_detalle(categoria: str, db: Session = Depends(get_db)):
    return kpi_service.get_desarrollo_detalle(db, categoria)


@router.get("/kpis/{kpi_id}/modal")
def kpi_modal(
    kpi_id: str,
    region: str | None = Query(None),
    anio: int | None = Query(None),
    trimestre: int | None = Query(None),
    mes: int | None = Query(None),
    categoria: str | None = Query(None),
    db: Session = Depends(get_db),
):
    _db_guard(db)
    try:
        return kpi_service.get_kpi_modal(
            db, kpi_id, region, anio, trimestre, mes, categoria
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
