def _fn(name, description, parameters):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


def _prop(tipo, descripcion):
    return {"type": tipo, "description": descripcion}


def herramientas_disponibles():
    return [
        _fn(
            "consultar_tarjetas_kpi",
            "Obtiene los 4 indicadores principales del balanced scorecard (margen neto, ROI, NPS y paises con presencia comercial) para un rango de anios, con su meta, porcentaje de cumplimiento y semaforo de estado.",
            {
                "type": "object",
                "properties": {
                    "anio_inicio": _prop("integer", "Anio inicial del rango, entre 2026 y 2030"),
                    "anio_fin": _prop("integer", "Anio final del rango, entre 2026 y 2030"),
                },
            },
        ),
        _fn(
            "consultar_desarrollo_por_categoria",
            "Obtiene el tiempo promedio de desarrollo de productos en meses, agrupado por categoria (iPhone, Mac, iPad, Apple Watch, AirPods).",
            {
                "type": "object",
                "properties": {
                    "anio_inicio": _prop("integer", "Anio inicial del rango de lanzamiento"),
                    "anio_fin": _prop("integer", "Anio final del rango de lanzamiento"),
                },
            },
        ),
        _fn(
            "consultar_detalle_desarrollo_categoria",
            "Obtiene el listado de productos de una categoria especifica con su tiempo de desarrollo en meses y si son valores atipicos.",
            {
                "type": "object",
                "properties": {
                    "categoria": _prop("string", "Nombre exacto de la categoria: iPhone, Mac, iPad, Apple Watch o AirPods"),
                    "anio_inicio": _prop("integer", "Anio inicial del rango de lanzamiento"),
                    "anio_fin": _prop("integer", "Anio final del rango de lanzamiento"),
                },
                "required": ["categoria"],
            },
        ),
        _fn(
            "consultar_capacitacion_vs_errores",
            "Obtiene los puntos mensuales de horas de capacitacion por empleado versus tasa de errores por region, junto con la correlacion estadistica.",
            {
                "type": "object",
                "properties": {
                    "anio_inicio": _prop("integer", "Anio inicial del rango"),
                    "anio_fin": _prop("integer", "Anio final del rango"),
                },
            },
        ),
        _fn(
            "consultar_satisfaccion_laboral",
            "Obtiene la serie historica anual del indice de satisfaccion laboral, de forma global o filtrada por region.",
            {
                "type": "object",
                "properties": {
                    "region": _prop("string", "Nombre exacto de una region para filtrar, opcional"),
                    "anio_inicio": _prop("integer", "Anio inicial del rango"),
                    "anio_fin": _prop("integer", "Anio final del rango"),
                },
            },
        ),
        _fn(
            "consultar_regiones_disponibles",
            "Obtiene el listado de nombres de todas las regiones comerciales registradas.",
            {"type": "object", "properties": {}},
        ),
        _fn(
            "consultar_margen_neto_historico",
            "Obtiene la serie trimestral historica del margen neto porcentual, de forma global o filtrada por region, junto con sus estadisticas.",
            {
                "type": "object",
                "properties": {
                    "region": _prop("string", "Nombre exacto de una region para filtrar, opcional"),
                },
            },
        ),
        _fn(
            "consultar_roi_historico",
            "Obtiene la serie trimestral historica del retorno de la inversion corporativo global junto con sus estadisticas.",
            {"type": "object", "properties": {}},
        ),
        _fn(
            "consultar_nps_historico",
            "Obtiene la serie trimestral historica del Net Promoter Score, de forma global o filtrada por region.",
            {
                "type": "object",
                "properties": {
                    "region": _prop("string", "Nombre exacto de una region para filtrar, opcional"),
                },
            },
        ),
        _fn(
            "consultar_paises_historico",
            "Obtiene la serie anual historica de cantidad de paises con presencia comercial.",
            {"type": "object", "properties": {}},
        ),
        _fn(
            "generar_proyeccion_2031",
            "Genera una proyeccion estadistica bayesiana al anio 2031 para una metrica del balanced scorecard, bajo un escenario real, positivista, pesimista o personalizado, retornando el punto medio esperado y su intervalo de credibilidad del 90 por ciento.",
            {
                "type": "object",
                "properties": {
                    "metrica": {
                        "type": "string",
                        "enum": [
                            "margen_neto",
                            "roi",
                            "nps",
                            "paises",
                            "satisfaccion",
                            "horas_capacitacion",
                            "tasa_errores",
                            "tiempo_desarrollo",
                        ],
                        "description": "Metrica a proyectar",
                    },
                    "escenario": {
                        "type": "string",
                        "enum": ["real", "positivista", "pesimista", "personalizado"],
                        "description": "Escenario de proyeccion, real no genera proyeccion",
                    },
                    "region": _prop("string", "Region para filtrar cuando la metrica lo permite, opcional"),
                    "categoria": _prop("string", "Categoria de producto, requerida solo cuando la metrica es tiempo_desarrollo"),
                    "tasa_cambio": _prop("number", "Pendiente anual personalizada, solo para escenario personalizado"),
                    "confianza": {
                        "type": "string",
                        "enum": ["baja", "media", "alta"],
                        "description": "Nivel de confianza del prior personalizado, solo para escenario personalizado",
                    },
                },
                "required": ["metrica", "escenario"],
            },
        ),
    ]