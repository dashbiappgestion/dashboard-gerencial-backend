import math
from sqlalchemy.orm import Session
from app.database import fetch_all, fetch_one

METAS = {
    "margen_neto": 28.0,
    "roi": 15.0,
    "nps": 80.0,
    "paises": 180.0,
    "tiempo_desarrollo": 18.0,
    "horas_capacitacion": 10.0,
    "satisfaccion": 85.0,
}


def _status(valor: float, meta: float, invertido: bool = False) -> str:
    if invertido:
        pct = (meta / valor * 100) if valor > 0 else 0
    else:
        pct = (valor / meta * 100) if meta > 0 else 0
    if pct >= 100:
        return "green"
    if pct >= 85:
        return "yellow"
    return "red"


def _pct_cumplimiento(valor: float, meta: float, invertido: bool = False) -> float:
    if invertido:
        return round((meta / valor * 100) if valor > 0 else 0, 1)
    return round((valor / meta * 100) if meta > 0 else 0, 1)


def get_periodo_actual(session: Session) -> dict:
    row = fetch_one(
        session,
        """
        SELECT anio, trimestre
        FROM dim_trimestre
        ORDER BY anio DESC, trimestre DESC
        LIMIT 1
        """,
    )
    return row or {"anio": 2030, "trimestre": 4}


def get_tarjetas(session: Session) -> dict:
    periodo = get_periodo_actual(session)
    anio = periodo["anio"]
    trimestre = periodo["trimestre"]

    margen = fetch_one(
        session,
        """
        SELECT ROUND(AVG(margen_neto_pct)::numeric, 2) AS valor
        FROM hechos_financiero
        WHERE anio = :anio AND trimestre = :trimestre
        """,
        {"anio": anio, "trimestre": trimestre},
    )
    roi = fetch_one(
        session,
        """
        SELECT roi_pct AS valor
        FROM hechos_corporativo
        WHERE anio = :anio AND trimestre = :trimestre
        """,
        {"anio": anio, "trimestre": trimestre},
    )
    nps = fetch_one(
        session,
        """
        SELECT ROUND(AVG(nps_score)::numeric, 2) AS valor
        FROM hechos_nps
        WHERE anio = :anio AND trimestre = :trimestre
        """,
        {"anio": anio, "trimestre": trimestre},
    )
    paises = fetch_one(
        session,
        """
        SELECT paises_con_presencia AS valor
        FROM vw_kpi_paises_anio
        WHERE anio = :anio
        """,
        {"anio": anio},
    )

    cards = []
    for key, label, suffix, decimals, meta, invertido in [
        ("margen_neto", "Margen Neto", "%", 1, METAS["margen_neto"], False),
        ("roi", "Retorno de la Inversión (ROI)", "%", 1, METAS["roi"], False),
        ("nps", "Net Promoter Score (NPS)", " pts", 1, METAS["nps"], False),
        ("paises", "Países con Presencia Comercial", "", 0, METAS["paises"], False),
    ]:
        source = {"margen_neto": margen, "roi": roi, "nps": nps, "paises": paises}[key]
        valor = (
            float(source["valor"]) if source and source["valor"] is not None else 0.0
        )
        pct = _pct_cumplimiento(valor, meta, invertido)
        cards.append(
            {
                "id": key,
                "label": label,
                "valor": valor,
                "meta": meta,
                "suffix": suffix,
                "decimals": decimals,
                "pct": pct,
                "status": _status(valor, meta, invertido),
            }
        )

    return {
        "periodo": {"anio": anio, "trimestre": trimestre},
        "tarjetas": cards,
    }


def get_desarrollo_categoria(session: Session) -> dict:
    rows = fetch_all(
        session,
        """
        SELECT categoria, promedio_meses, n_productos
        FROM vw_kpi_desarrollo_categoria
        ORDER BY categoria
        """,
    )
    colores = {
        "iPhone": "var(--ink)",
        "Mac": "var(--gray-900)",
        "iPad": "var(--gray-700)",
        "Apple Watch": "var(--gray-500)",
        "AirPods": "var(--gray-300)",
    }
    total = sum(float(r["promedio_meses"]) for r in rows) or 1
    categorias = []
    for row in rows:
        meses = float(row["promedio_meses"])
        categorias.append(
            {
                "categoria": row["categoria"],
                "promedio_meses": meses,
                "n_productos": int(row["n_productos"]),
                "pct": round(meses / total * 100, 1),
                "color": colores.get(row["categoria"], "var(--gray-500)"),
            }
        )
    promedio_global = round(total / len(rows), 1) if rows else 0
    meta = METAS["tiempo_desarrollo"]
    return {
        "categorias": categorias,
        "promedio_global": promedio_global,
        "meta": meta,
        "status": _status(promedio_global, meta, invertido=True),
    }


def get_capacitacion_errores(session: Session) -> dict:
    puntos = fetch_all(
        session,
        """
        SELECT anio, mes, nombre_region, horas_capacitacion, tasa_errores
        FROM vw_kpi_capacitacion_errores
        ORDER BY anio, mes, nombre_region
        """,
    )
    stats = fetch_one(
        session,
        """
        SELECT n_pares, r_pearson, r_cuadrado, pendiente, intercepto
        FROM vw_kpi_capacitacion_errores_stats
        """,
    )
    for p in puntos:
        p["horas_capacitacion"] = float(p["horas_capacitacion"])
        p["tasa_errores"] = float(p["tasa_errores"])
    return {
        "puntos": puntos,
        "stats": stats or {},
        "meta_horas": METAS["horas_capacitacion"],
    }


def get_satisfaccion(session: Session, region: str | None = None) -> dict:
    params: dict = {}
    region_filter = ""
    if region:
        region_filter = "AND r.nombre_region = :region"
        params["region"] = region

    rows = fetch_all(
        session,
        f"""
        SELECT c.anio, r.nombre_region,
               ROUND(AVG(c.indice_satisfaccion)::numeric, 2) AS valor
        FROM hechos_clima_laboral c
        JOIN dim_region r ON r.region_id = c.region_id
        WHERE 1=1 {region_filter}
        GROUP BY c.anio, r.nombre_region
        ORDER BY c.anio, r.nombre_region
        """,
        params,
    )

    if not region:
        agg = fetch_all(
            session,
            """
            SELECT anio, ROUND(AVG(indice_satisfaccion)::numeric, 2) AS valor
            FROM hechos_clima_laboral
            GROUP BY anio
            ORDER BY anio
            """,
        )
        serie = [{"anio": int(r["anio"]), "valor": float(r["valor"])} for r in agg]
    else:
        serie = [
            {"anio": int(r["anio"]), "valor": float(r["valor"])}
            for r in rows
            if r["nombre_region"] == region
        ]

    ultimo = serie[-1]["valor"] if serie else 0
    meta = METAS["satisfaccion"]
    return {
        "serie": serie,
        "meta": meta,
        "ultimo_valor": ultimo,
        "status": _status(ultimo, meta),
        "regiones": get_regiones(session),
    }


def get_regiones(session: Session) -> list[str]:
    rows = fetch_all(
        session,
        "SELECT nombre_region FROM dim_region ORDER BY region_id",
    )
    return [r["nombre_region"] for r in rows]


def get_margen_historico(session: Session, region: str | None = None) -> dict:
    params: dict = {}
    region_filter = ""
    if region:
        region_filter = "AND r.nombre_region = :region"
        params["region"] = region

    rows = fetch_all(
        session,
        f"""
        SELECT f.anio, f.trimestre, r.nombre_region, f.margen_neto_pct AS valor
        FROM hechos_financiero f
        JOIN dim_region r ON r.region_id = f.region_id
        WHERE 1=1 {region_filter}
        ORDER BY f.anio, f.trimestre
        """,
        params,
    )
    stats = (
        fetch_one(
            session,
            """
        SELECT * FROM vw_kpi_margen_neto_stats
        WHERE (:region IS NULL OR nombre_region = :region)
        LIMIT 1
        """,
            {"region": region},
        )
        if region
        else fetch_one(session, "SELECT * FROM vw_kpi_margen_neto_stats_global")
    )

    return {"serie": rows, "stats": stats}


def get_roi_historico(session: Session) -> dict:
    rows = fetch_all(
        session,
        """
        SELECT anio, trimestre, roi_pct AS valor
        FROM hechos_corporativo
        ORDER BY anio, trimestre
        """,
    )
    stats = fetch_one(session, "SELECT * FROM vw_kpi_roi_stats")
    return {"serie": rows, "stats": stats}


def get_nps_historico(session: Session, region: str | None = None) -> dict:
    params: dict = {}
    region_filter = ""
    if region:
        region_filter = "AND r.nombre_region = :region"
        params["region"] = region

    rows = fetch_all(
        session,
        f"""
        SELECT n.anio, n.trimestre, r.nombre_region, n.nps_score AS valor
        FROM hechos_nps n
        JOIN dim_region r ON r.region_id = n.region_id
        WHERE 1=1 {region_filter}
        ORDER BY n.anio, n.trimestre
        """,
        params,
    )
    stats = (
        fetch_one(
            session,
            """
        SELECT * FROM vw_kpi_nps_stats
        WHERE (:region IS NULL OR nombre_region = :region)
        LIMIT 1
        """,
            {"region": region},
        )
        if region
        else None
    )

    return {"serie": rows, "stats": stats}


def get_paises_historico(session: Session) -> dict:
    rows = fetch_all(
        session,
        """
        SELECT anio, paises_con_presencia AS valor
        FROM vw_kpi_paises_anio
        ORDER BY anio
        """,
    )
    stats = fetch_one(session, "SELECT * FROM vw_kpi_paises_stats")
    return {"serie": rows, "stats": stats}


def get_desarrollo_detalle(session: Session, categoria: str) -> dict:
    productos = fetch_all(
        session,
        """
        SELECT nombre_producto, tiempo_desarrollo_meses,
               fecha_inicio_desarrollo, fecha_lanzamiento
        FROM dim_producto
        WHERE categoria = :categoria
        ORDER BY fecha_lanzamiento
        """,
        {"categoria": categoria},
    )
    stats = fetch_one(
        session,
        """
        SELECT * FROM vw_kpi_desarrollo_categoria
        WHERE categoria = :categoria
        """,
        {"categoria": categoria},
    )
    for p in productos:
        p["tiempo_desarrollo_meses"] = int(p["tiempo_desarrollo_meses"])
        lim_inf = float(stats["limite_inferior"]) if stats else None
        lim_sup = float(stats["limite_superior"]) if stats else None
        val = float(p["tiempo_desarrollo_meses"])
        p["outlier"] = bool(
            lim_inf is not None
            and lim_sup is not None
            and (val < lim_inf or val > lim_sup)
        )
    return {
        "productos": productos,
        "stats": stats,
        "categoria": categoria,
        "meta": METAS["tiempo_desarrollo"],
    }


KPI_MODAL_CONFIG = {
    "margen_neto": {
        "titulo": "Margen Neto",
        "frecuencia": "trimestral",
        "region": True,
        "meta": METAS["margen_neto"],
        "suffix": "%",
        "decimals": 1,
    },
    "roi": {
        "titulo": "Retorno de la Inversión (ROI)",
        "frecuencia": "trimestral",
        "region": False,
        "region_msg": "Este KPI se gestiona a nivel corporativo global",
        "meta": METAS["roi"],
        "suffix": "%",
        "decimals": 1,
    },
    "nps": {
        "titulo": "Net Promoter Score (NPS)",
        "frecuencia": "trimestral",
        "region": True,
        "meta": METAS["nps"],
        "suffix": " pts",
        "decimals": 1,
    },
    "paises": {
        "titulo": "Países con Presencia Comercial",
        "frecuencia": "anual",
        "region": False,
        "region_msg": "Conteo global acumulado, no aplica por región",
        "meta": METAS["paises"],
        "suffix": "",
        "decimals": 0,
    },
    "desarrollo": {
        "titulo": "Tiempo de Desarrollo de Productos",
        "frecuencia": "evento",
        "region": False,
        "region_msg": "El desarrollo de producto es centralizado, no regional",
        "meta": METAS["tiempo_desarrollo"],
        "suffix": " m",
        "decimals": 0,
    },
    "capacitacion_errores": {
        "titulo": "Capacitación vs. Tasa de Errores",
        "frecuencia": "mensual",
        "region": True,
        "meta": METAS["horas_capacitacion"],
        "suffix": "",
        "decimals": 2,
    },
    "satisfaccion": {
        "titulo": "Índice de Satisfacción Laboral",
        "frecuencia": "anual",
        "region": True,
        "meta": METAS["satisfaccion"],
        "suffix": " pts",
        "decimals": 1,
    },
}


def _float_stats(stats: dict | None) -> dict | None:
    if not stats:
        return None
    return {
        k: (
            float(v)
            if v is not None and k != "nombre_region" and k != "categoria"
            else v
        )
        for k, v in stats.items()
    }


def _mark_outliers(
    serie: list[dict], lim_inf: float | None, lim_sup: float | None
) -> list[dict]:
    for row in serie:
        val = float(row["valor"])
        row["outlier"] = bool(
            lim_inf is not None
            and lim_sup is not None
            and (val < lim_inf or val > lim_sup)
        )
    return serie


def _filter_serie(
    serie: list[dict],
    anio: int | None,
    trimestre: int | None,
    mes: int | None,
    freq: str,
) -> list[dict]:
    result = serie
    if anio is not None:
        result = [r for r in result if int(r["anio"]) == anio]
    if freq == "trimestral" and trimestre is not None:
        result = [r for r in result if int(r["trimestre"]) == trimestre]
    if freq == "mensual" and mes is not None:
        result = [r for r in result if int(r["mes"]) == mes]
    return result


def _build_trend_serie(rows: list[dict], freq: str) -> list[dict]:
    serie = []
    for i, row in enumerate(rows):
        if freq == "trimestral":
            label = f"{row['anio']}-Q{row['trimestre']}"
            x = int(row["anio"]) * 4 + int(row["trimestre"])
        elif freq == "mensual":
            label = f"{row['anio']}-{int(row['mes']):02d}"
            x = int(row["anio"]) * 12 + int(row["mes"])
        else:
            label = str(row["anio"])
            x = int(row["anio"])
        serie.append(
            {
                "label": label,
                "valor": float(row["valor"]),
                "x": x,
                "anio": int(row["anio"]),
                **(
                    {"trimestre": int(row["trimestre"])} if freq == "trimestral" else {}
                ),
                **({"mes": int(row["mes"])} if freq == "mensual" else {}),
            }
        )
    return serie


def get_anios_disponibles(session: Session) -> list[int]:
    rows = fetch_all(session, "SELECT anio FROM dim_anio ORDER BY anio")
    return [int(r["anio"]) for r in rows]


def get_kpi_modal(
    session: Session,
    kpi_id: str,
    region: str | None = None,
    anio: int | None = None,
    trimestre: int | None = None,
    mes: int | None = None,
    categoria: str | None = None,
) -> dict:
    if kpi_id not in KPI_MODAL_CONFIG:
        raise ValueError(f"KPI desconocido: {kpi_id}")

    config = KPI_MODAL_CONFIG[kpi_id]
    freq = config["frecuencia"]
    regiones = get_regiones(session)
    anios = get_anios_disponibles(session)

    base = {
        "kpi_id": kpi_id,
        "config": config,
        "filtros": {
            "anios": anios if freq != "evento" else [],
            "trimestres": [1, 2, 3, 4] if freq == "trimestral" else [],
            "meses": list(range(1, 13)) if freq == "mensual" else [],
            "regiones": regiones if config["region"] else [],
        },
        "filtros_activos": {
            "region": region,
            "anio": anio,
            "trimestre": trimestre,
            "mes": mes,
            "categoria": categoria,
        },
    }

    if kpi_id == "margen_neto":
        raw = get_margen_historico(session, region)
        if region:
            agg = {}
            for row in raw["serie"]:
                key = (row["anio"], row["trimestre"])
                agg[key] = float(row["valor"])
            rows = [
                {"anio": k[0], "trimestre": k[1], "valor": v}
                for k, v in sorted(agg.items())
            ]
            stats = raw["stats"]
        else:
            rows = fetch_all(
                session,
                """
                SELECT anio, trimestre, ROUND(AVG(margen_neto_pct)::numeric, 2) AS valor
                FROM hechos_financiero
                GROUP BY anio, trimestre
                ORDER BY anio, trimestre
                """,
            )
            stats = fetch_one(session, "SELECT * FROM vw_kpi_margen_neto_stats_global")
            
        serie = _build_trend_serie(rows, freq)
        stats = _float_stats(stats)
        serie = _mark_outliers(
            serie,
            stats.get("limite_inferior") if stats else None,
            stats.get("limite_superior") if stats else None,
        )
        serie = _filter_serie(serie, anio, trimestre, mes, freq)
        return {
            **base,
            "tipo": "tendencia",
            "serie": serie,
            "stats": stats,
            "meta": config["meta"],
        }

    if kpi_id == "roi":
        raw = get_roi_historico(session)
        serie = _build_trend_serie(raw["serie"], freq)
        stats = _float_stats(raw["stats"])
        serie = _mark_outliers(
            serie,
            stats.get("limite_inferior") if stats else None,
            stats.get("limite_superior") if stats else None,
        )
        serie = _filter_serie(serie, anio, trimestre, mes, freq)
        return {
            **base,
            "tipo": "tendencia",
            "serie": serie,
            "stats": stats,
            "meta": config["meta"],
        }

    if kpi_id == "nps":
        raw = get_nps_historico(session, region)
        if region:
            rows = [
                {"anio": r["anio"], "trimestre": r["trimestre"], "valor": r["valor"]}
                for r in raw["serie"]
            ]
            stats = _float_stats(raw["stats"])
        else:
            rows = fetch_all(
                session,
                """
                SELECT anio, trimestre, ROUND(AVG(nps_score)::numeric, 2) AS valor
                FROM hechos_nps
                GROUP BY anio, trimestre
                ORDER BY anio, trimestre
                """,
            )
            stats = fetch_one(session, "SELECT * FROM vw_kpi_nps_stats_global")
            stats = _float_stats(stats)
            
        serie = _build_trend_serie(rows, freq)
        serie = _mark_outliers(
            serie,
            stats.get("limite_inferior") if stats else None,
            stats.get("limite_superior") if stats else None,
        )
        serie = _filter_serie(serie, anio, trimestre, mes, freq)
        return {
            **base,
            "tipo": "tendencia",
            "serie": serie,
            "stats": stats,
            "meta": config["meta"],
        }

    if kpi_id == "paises":
        raw = get_paises_historico(session)
        serie = _build_trend_serie(raw["serie"], freq)
        stats = _float_stats(raw["stats"])
        serie = _filter_serie(serie, anio, trimestre, mes, freq)
        return {
            **base,
            "tipo": "tendencia",
            "serie": serie,
            "stats": stats,
            "meta": config["meta"],
        }

    if kpi_id == "satisfaccion":
        raw = get_satisfaccion(session, region)
        serie = _build_trend_serie(
            [{"anio": p["anio"], "valor": p["valor"]} for p in raw["serie"]],
            freq,
        )
        stats_row = (
            fetch_one(
                session,
                """
            SELECT * FROM vw_kpi_clima_laboral_stats
            WHERE nombre_region = :region
            LIMIT 1
            """,
                {"region": region},
            )
            if region
            else fetch_one(session, "SELECT * FROM vw_kpi_clima_laboral_stats_global")
        )
        stats = _float_stats(stats_row)
        serie = _mark_outliers(
            serie,
            stats.get("limite_inferior") if stats else None,
            stats.get("limite_superior") if stats else None,
        )
        serie = _filter_serie(serie, anio, trimestre, mes, freq)
        return {
            **base,
            "tipo": "tendencia",
            "serie": serie,
            "stats": stats,
            "meta": config["meta"],
        }

    if kpi_id == "desarrollo":
        cat = categoria or "iPhone"
        detalle = get_desarrollo_detalle(session, cat)
        serie = [
            {
                "label": p["nombre_producto"],
                "valor": float(p["tiempo_desarrollo_meses"]),
                "x": i,
                "outlier": p["outlier"],
            }
            for i, p in enumerate(detalle["productos"])
        ]
        return {
            **base,
            "tipo": "productos",
            "serie": serie,
            "stats": _float_stats(detalle["stats"]),
            "meta": config["meta"],
            "categoria": cat,
            "categorias": [
                c["categoria"] for c in get_desarrollo_categoria(session)["categorias"]
            ],
        }

    if kpi_id == "capacitacion_errores":
        return get_capacitacion_errores_modal(session, region, anio, mes, base)

    raise ValueError(f"KPI no soportado: {kpi_id}")


def get_capacitacion_errores_modal(
    session: Session,
    region: str | None,
    anio: int | None,
    mes: int | None,
    base: dict,
) -> dict:
    params: dict = {}
    filters = []
    if region:
        filters.append("nombre_region = :region")
        params["region"] = region
    if anio is not None:
        filters.append("anio = :anio")
        params["anio"] = anio
    if mes is not None:
        filters.append("mes = :mes")
        params["mes"] = mes
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    puntos = fetch_all(
        session,
        f"""
        SELECT anio, mes, nombre_region, horas_capacitacion, tasa_errores
        FROM vw_kpi_capacitacion_errores
        {where}
        ORDER BY anio, mes, nombre_region
        """,
        params,
    )

    xs = [float(p["horas_capacitacion"]) for p in puntos]
    ys = [float(p["tasa_errores"]) for p in puntos]
    n = len(xs)

    if n > 1:
        mean_x, mean_y = sum(xs) / n, sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        var_x = sum((x - mean_x) ** 2 for x in xs)
        var_y = sum((y - mean_y) ** 2 for y in ys)

        slope = cov / var_x if var_x else 0
        intercept = mean_y - slope * mean_x
        r_pearson = cov / math.sqrt(var_x * var_y) if var_x and var_y else 0

        std_dev_y = math.sqrt(var_y / (n - 1)) if n > 1 else 0
        err = std_dev_y / math.sqrt(n)
    else:
        slope, intercept, r_pearson, err = 0, 0, 0, 0

    stats = {
        "n_pares": n,
        "r_pearson": round(r_pearson, 4),
        "pendiente": round(slope, 4),
        "intercepto": round(intercept, 4),
        "error_estandar": round(err, 4),
    }

    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    if residuals:
        sorted_r = sorted(residuals)
        q1 = sorted_r[int(n * 0.25)]
        q3 = sorted_r[int(n * 0.75)]
        ric = q3 - q1
        lim_inf = q1 - 1.5 * ric
        lim_sup = q3 + 1.5 * ric
    else:
        lim_inf = lim_sup = 0

    enriched = []
    for p, res in zip(puntos, residuals):
        enriched.append(
            {
                "anio": int(p["anio"]),
                "mes": int(p["mes"]),
                "nombre_region": p["nombre_region"],
                "horas_capacitacion": float(p["horas_capacitacion"]),
                "tasa_errores": float(p["tasa_errores"]),
                "outlier": res < lim_inf or res > lim_sup,
            }
        )

    x_min, x_max = (min(xs), max(xs)) if xs else (0, 10)
    regresion = [
        {"x": x_min, "y": intercept + slope * x_min},
        {"x": x_max, "y": intercept + slope * x_max},
    ]
    banda = [
        {
            "x": x_min,
            "y_upper": intercept + slope * x_min + err,
            "y_lower": intercept + slope * x_min - err,
        },
        {
            "x": x_max,
            "y_upper": intercept + slope * x_max + err,
            "y_lower": intercept + slope * x_max - err,
        },
    ]

    return {
        **base,
        "tipo": "dispersion",
        "puntos": enriched,
        "stats": stats,
        "regresion": regresion,
        "banda": banda,
        "meta": KPI_MODAL_CONFIG["capacitacion_errores"]["meta"],
    }