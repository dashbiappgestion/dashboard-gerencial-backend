from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import kpi_service
from app.services.forecast_service import run_bayesian_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

class CustomParams(BaseModel):
    tasa_cambio: float
    confianza: str = "media"

class ForecastParams(BaseModel):
    margen_neto: CustomParams | None = None
    roi: CustomParams | None = None
    nps: CustomParams | None = None
    paises: CustomParams | None = None
    satisfaccion: CustomParams | None = None
    horas_capacitacion: CustomParams | None = None
    tasa_errores: CustomParams | None = None
    tiempo_desarrollo: dict[str, CustomParams] | None = None

class ForecastRequest(BaseModel):
    escenario: str
    region: str | None = None
    parametros_personalizados: ForecastParams | None = None

DIRECCION_MEJORA = {
    "margen_neto": 1,
    "roi": 1,
    "nps": 1,
    "paises": 1,
    "satisfaccion": 1,
    "horas_capacitacion": 1,
    "tasa_errores": -1,
    "tiempo_desarrollo": -1,
}

@router.post("/2031")
def forecast_2031(req: ForecastRequest, db: Session = Depends(get_db)):
    if req.escenario == "real":
        return {}

    response = {}
    custom = req.parametros_personalizados

    def do_forecast(key: str, xs: list, ys: list, x_star: float, c_params: CustomParams | None):
        return run_bayesian_forecast(
            xs=xs,
            ys=ys,
            x_star=x_star,
            escenario=req.escenario,
            direccion_mejora=DIRECCION_MEJORA[key],
            custom_params=c_params.model_dump() if c_params else None
        )

    data_margen = kpi_service.get_margen_historico(db, req.region)
    if data_margen and "serie" in data_margen:
        xs = [p["anio"] + (p["trimestre"] - 1)/4 for p in data_margen["serie"]]
        ys = [p["valor"] for p in data_margen["serie"]]
        response["margen_neto"] = do_forecast("margen_neto", xs, ys, 2031.5, custom.margen_neto if custom else None)

    data_roi = kpi_service.get_roi_historico(db)
    if data_roi and "serie" in data_roi:
        xs = [p["anio"] + (p["trimestre"] - 1)/4 for p in data_roi["serie"]]
        ys = [p["valor"] for p in data_roi["serie"]]
        response["roi"] = do_forecast("roi", xs, ys, 2031.5, custom.roi if custom else None)

    data_nps = kpi_service.get_nps_historico(db, req.region)
    if data_nps and "serie" in data_nps:
        xs = [p["anio"] + (p["trimestre"] - 1)/4 for p in data_nps["serie"]]
        ys = [p["valor"] for p in data_nps["serie"]]
        response["nps"] = do_forecast("nps", xs, ys, 2031.5, custom.nps if custom else None)

    data_paises = kpi_service.get_paises_historico(db)
    if data_paises and "serie" in data_paises:
        xs = [p["anio"] for p in data_paises["serie"]]
        ys = [p["valor"] for p in data_paises["serie"]]
        response["paises"] = do_forecast("paises", xs, ys, 2031, custom.paises if custom else None)

    data_sat = kpi_service.get_satisfaccion(db, req.region)
    if data_sat and "serie" in data_sat:
        xs = [p["anio"] for p in data_sat["serie"]]
        ys = [p["valor"] for p in data_sat["serie"]]
        response["satisfaccion"] = do_forecast("satisfaccion", xs, ys, 2031, custom.satisfaccion if custom else None)

    data_cap = kpi_service.get_capacitacion_errores_modal(db, req.region, None, None, {})
    if data_cap and "puntos" in data_cap:
        xs_t = [p["anio"] + (p["mes"] - 1)/12 for p in data_cap["puntos"]]
        ys_horas = [p["horas_capacitacion"] for p in data_cap["puntos"]]
        ys_errores = [p["tasa_errores"] for p in data_cap["puntos"]]
        response["horas_capacitacion"] = do_forecast("horas_capacitacion", xs_t, ys_horas, 2031.5, custom.horas_capacitacion if custom else None)
        response["tasa_errores"] = do_forecast("tasa_errores", xs_t, ys_errores, 2031.5, custom.tasa_errores if custom else None)

    data_cats = kpi_service.get_desarrollo_categoria(db)
    desarrollo_res = {}
    if data_cats and "categorias" in data_cats:
        for c in data_cats["categorias"]:
            cat_name = c["categoria"]
            detalle = kpi_service.get_desarrollo_detalle(db, cat_name)
            xs_cat = []
            for p in detalle["productos"]:
                try:
                    yr = int(str(p["fecha_lanzamiento"]).split("-")[0])
                    xs_cat.append(yr)
                except:
                    pass
            ys_cat = [p["tiempo_desarrollo_meses"] for p in detalle["productos"]]
            if len(xs_cat) == len(ys_cat):
                c_params = custom.tiempo_desarrollo.get(cat_name) if custom and custom.tiempo_desarrollo else None
                desarrollo_res[cat_name] = do_forecast("tiempo_desarrollo", xs_cat, ys_cat, 2031, c_params)
    response["tiempo_desarrollo"] = desarrollo_res

    return response
