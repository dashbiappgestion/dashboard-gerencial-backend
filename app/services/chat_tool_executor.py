import json
from sqlalchemy.orm import Session
from app.services import kpi_service
from app.services.forecast_service import run_bayesian_forecast

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


def ejecutar_herramienta(nombre: str, argumentos_json: str, db: Session) -> str:
    try:
        args = json.loads(argumentos_json) if argumentos_json else {}
    except Exception:
        args = {}
    try:
        if nombre == "consultar_tarjetas_kpi":
            resultado = kpi_service.get_tarjetas(db, args.get("anio_inicio"), args.get("anio_fin"))
        elif nombre == "consultar_desarrollo_por_categoria":
            resultado = kpi_service.get_desarrollo_categoria(db, args.get("anio_inicio"), args.get("anio_fin"))
        elif nombre == "consultar_detalle_desarrollo_categoria":
            resultado = kpi_service.get_desarrollo_detalle(db, args["categoria"], args.get("anio_inicio"), args.get("anio_fin"))
        elif nombre == "consultar_capacitacion_vs_errores":
            resultado = kpi_service.get_capacitacion_errores(db, args.get("anio_inicio"), args.get("anio_fin"))
        elif nombre == "consultar_satisfaccion_laboral":
            resultado = kpi_service.get_satisfaccion(db, args.get("region"), args.get("anio_inicio"), args.get("anio_fin"))
        elif nombre == "consultar_regiones_disponibles":
            resultado = {"regiones": kpi_service.get_regiones(db)}
        elif nombre == "consultar_margen_neto_historico":
            resultado = kpi_service.get_margen_historico(db, args.get("region"))
        elif nombre == "consultar_roi_historico":
            resultado = kpi_service.get_roi_historico(db)
        elif nombre == "consultar_nps_historico":
            resultado = kpi_service.get_nps_historico(db, args.get("region"))
        elif nombre == "consultar_paises_historico":
            resultado = kpi_service.get_paises_historico(db)
        elif nombre == "generar_proyeccion_2031":
            resultado = _generar_proyeccion(db, args)
        else:
            resultado = {"ok": False, "error": "herramienta_desconocida"}
    except Exception as exc:
        resultado = {"ok": False, "error": str(exc)}
    return json.dumps(resultado, default=str, ensure_ascii=False)


def _generar_proyeccion(db: Session, args: dict) -> dict:
    metrica = args.get("metrica")
    escenario = args.get("escenario", "real")
    region = args.get("region")
    categoria = args.get("categoria")
    if escenario == "real" or metrica not in DIRECCION_MEJORA:
        return {"ok": False, "error": "escenario_o_metrica_invalido"}
    custom_params = None
    if escenario == "personalizado":
        custom_params = {
            "tasa_cambio": args.get("tasa_cambio", 0),
            "confianza": args.get("confianza", "media"),
        }
    if metrica == "margen_neto":
        serie = kpi_service.get_margen_historico(db, region).get("serie", [])
        xs = [p["anio"] + (p["trimestre"] - 1) / 4 for p in serie]
        ys = [p["valor"] for p in serie]
        x_star = 2031.5
    elif metrica == "roi":
        serie = kpi_service.get_roi_historico(db).get("serie", [])
        xs = [p["anio"] + (p["trimestre"] - 1) / 4 for p in serie]
        ys = [p["valor"] for p in serie]
        x_star = 2031.5
    elif metrica == "nps":
        serie = kpi_service.get_nps_historico(db, region).get("serie", [])
        xs = [p["anio"] + (p["trimestre"] - 1) / 4 for p in serie]
        ys = [p["valor"] for p in serie]
        x_star = 2031.5
    elif metrica == "paises":
        serie = kpi_service.get_paises_historico(db).get("serie", [])
        xs = [p["anio"] for p in serie]
        ys = [p["valor"] for p in serie]
        x_star = 2031
    elif metrica == "satisfaccion":
        serie = kpi_service.get_satisfaccion(db, region).get("serie", [])
        xs = [p["anio"] for p in serie]
        ys = [p["valor"] for p in serie]
        x_star = 2031
    elif metrica in ("horas_capacitacion", "tasa_errores"):
        puntos = kpi_service.get_capacitacion_errores_modal(db, region, None, None, {}).get("puntos", [])
        xs = [p["anio"] + (p["mes"] - 1) / 12 for p in puntos]
        ys = [p["horas_capacitacion"] if metrica == "horas_capacitacion" else p["tasa_errores"] for p in puntos]
        x_star = 2031.5
    elif metrica == "tiempo_desarrollo":
        if not categoria:
            return {"ok": False, "error": "categoria_requerida"}
        productos = kpi_service.get_desarrollo_detalle(db, categoria).get("productos", [])
        xs, ys = [], []
        for p in productos:
            try:
                anio_lanz = int(str(p["fecha_lanzamiento"]).split("-")[0])
            except Exception:
                continue
            xs.append(anio_lanz)
            ys.append(p["tiempo_desarrollo_meses"])
        x_star = 2031
    else:
        return {"ok": False, "error": "metrica_no_soportada"}
    resultado = run_bayesian_forecast(
        xs=xs,
        ys=ys,
        x_star=x_star,
        escenario=escenario,
        direccion_mejora=DIRECCION_MEJORA[metrica],
        custom_params=custom_params,
    )
    if resultado is None:
        return {"ok": False, "error": "datos_insuficientes"}
    resultado["ok"] = True
    resultado["metrica"] = metrica
    resultado["escenario"] = escenario
    return resultado