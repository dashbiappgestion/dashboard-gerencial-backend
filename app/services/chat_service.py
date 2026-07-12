import json
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import fetch_all, fetch_one
from app.services.cerebras_service import cerebras_api_service
from app.services.chat_tools import herramientas_disponibles
from app.services.chat_tool_executor import ejecutar_herramienta

MAX_MENSAJES_USUARIO = 8
MAX_RONDAS_HERRAMIENTAS = 6
RESPUESTA_FALLBACK = "No puedo realizar ello."
SYSTEM_PROMPT = (
    "Eres el asistente virtual del Dashboard Gerencial de Apple Inc. "
    "Ayudas a gerentes a interpretar el balanced scorecard: margen neto, ROI, NPS, paises con presencia comercial, "
    "tiempo de desarrollo de productos, capacitacion versus tasa de errores, y satisfaccion laboral. "
    "Usa siempre las herramientas disponibles para obtener datos reales antes de responder cifras. "
    "Cuando el usuario pida una proyeccion, tendencia futura o escenario, usa la herramienta generar_proyeccion_2031. "
    "Responde siempre en espanol, en formato Markdown, de forma clara, breve y orientada a negocio. "
    "Si una pregunta no tiene relacion con este dashboard, indica amablemente que solo puedes ayudar con temas del dashboard gerencial."
)


def _crear_sesion(db: Session, cliente_id: str) -> dict:
    session_id = str(uuid.uuid4())
    db.execute(
        text(
            """
            INSERT INTO chat_sesiones (session_id, cliente_id, contador_clave, mensajes_usuario, max_mensajes_usuario, cerrada, mensajes)
            VALUES (:session_id, :cliente_id, 0, 0, :max_msg, FALSE, '[]'::jsonb)
            """
        ),
        {"session_id": session_id, "cliente_id": cliente_id, "max_msg": MAX_MENSAJES_USUARIO},
    )
    db.commit()
    return fetch_one(db, "SELECT * FROM chat_sesiones WHERE session_id = :sid", {"sid": session_id})


def _sesion_activa(db: Session, cliente_id: str) -> dict:
    fila = fetch_one(
        db,
        """
        SELECT * FROM chat_sesiones
        WHERE cliente_id = :cliente_id AND cerrada = FALSE
        ORDER BY actualizado_en DESC
        LIMIT 1
        """,
        {"cliente_id": cliente_id},
    )
    if fila:
        return fila
    return _crear_sesion(db, cliente_id)


def _sesion_por_id(db: Session, cliente_id: str, session_id: str) -> dict | None:
    return fetch_one(
        db,
        "SELECT * FROM chat_sesiones WHERE session_id = :sid AND cliente_id = :cid",
        {"sid": session_id, "cid": cliente_id},
    )


def _serializar_sesion(fila: dict) -> dict:
    mensajes = fila["mensajes"] or []
    return {
        "sessionId": str(fila["session_id"]),
        "closed": fila["cerrada"],
        "userMessageCount": fila["mensajes_usuario"],
        "maxUserMessages": fila["max_mensajes_usuario"],
        "canContinue": (not fila["cerrada"]) and fila["mensajes_usuario"] < fila["max_mensajes_usuario"],
        "createdAt": fila["creado_en"],
        "updatedAt": fila["actualizado_en"],
        "messages": mensajes,
    }


def obtener_sesion_ui(db: Session, cliente_id: str) -> dict:
    return _serializar_sesion(_sesion_activa(db, cliente_id))


def nueva_sesion_ui(db: Session, cliente_id: str) -> dict:
    return _serializar_sesion(_crear_sesion(db, cliente_id))


def listar_sesiones_ui(db: Session, cliente_id: str) -> list[dict]:
    filas = fetch_all(
        db,
        """
        SELECT session_id, creado_en, actualizado_en, cerrada, mensajes_usuario, max_mensajes_usuario, mensajes
        FROM chat_sesiones
        WHERE cliente_id = :cliente_id
        ORDER BY actualizado_en DESC
        LIMIT 30
        """,
        {"cliente_id": cliente_id},
    )
    items = []
    for f in filas:
        mensajes = f["mensajes"] or []
        preview = "Nueva conversacion"
        for m in mensajes:
            if m.get("sender") == "USER":
                preview = m.get("content", "")[:80]
                break
        items.append(
            {
                "sessionId": str(f["session_id"]),
                "createdAt": f["creado_en"],
                "updatedAt": f["actualizado_en"],
                "closed": f["cerrada"],
                "userMessageCount": f["mensajes_usuario"],
                "maxUserMessages": f["max_mensajes_usuario"],
                "preview": preview,
                "canContinue": (not f["cerrada"]) and f["mensajes_usuario"] < f["max_mensajes_usuario"],
            }
        )
    return items


def obtener_sesion_por_id_ui(db: Session, cliente_id: str, session_id: str) -> dict:
    fila = _sesion_por_id(db, cliente_id, session_id)
    if not fila:
        raise ValueError("sesion_no_encontrada")
    return _serializar_sesion(fila)


def enviar_mensaje(db: Session, cliente_id: str, session_id: str | None, mensaje: str) -> dict:
    fila = _sesion_por_id(db, cliente_id, session_id) if session_id else None
    if not fila:
        fila = _sesion_activa(db, cliente_id)
    if fila["cerrada"] or fila["mensajes_usuario"] >= fila["max_mensajes_usuario"]:
        return {
            "sessionId": str(fila["session_id"]),
            "reply": "Esta conversacion alcanzo el limite de mensajes. Inicia un nuevo chat para continuar.",
            "closed": True,
            "sessionExpired": True,
            "messages": fila["mensajes"] or [],
        }
    mensajes = list(fila["mensajes"] or [])
    mensajes.append({"sender": "USER", "content": mensaje.strip()})
    llm_messages = _construir_mensajes_llm(mensajes)
    reply, contador_clave = _ejecutar_ciclo_llm(db, fila["contador_clave"], llm_messages)
    mensajes.append({"sender": "ASSISTANT", "content": reply})
    nuevos_mensajes_usuario = fila["mensajes_usuario"] + 1
    cerrada = nuevos_mensajes_usuario >= fila["max_mensajes_usuario"]
    db.execute(
        text(
            """
            UPDATE chat_sesiones
            SET mensajes = :mensajes, mensajes_usuario = :mu, contador_clave = :cc, cerrada = :cerrada, actualizado_en = now()
            WHERE session_id = :sid
            """
        ),
        {
            "mensajes": json.dumps(mensajes, ensure_ascii=False),
            "mu": nuevos_mensajes_usuario,
            "cc": contador_clave,
            "cerrada": cerrada,
            "sid": str(fila["session_id"]),
        },
    )
    db.commit()
    return {
        "sessionId": str(fila["session_id"]),
        "reply": reply,
        "closed": cerrada,
        "sessionExpired": False,
        "messages": mensajes,
    }


def _construir_mensajes_llm(mensajes_ui: list[dict]) -> list[dict]:
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in mensajes_ui:
        rol = "user" if m.get("sender") == "USER" else "assistant"
        llm_messages.append({"role": rol, "content": m.get("content", "")})
    return llm_messages


def _ejecutar_ciclo_llm(db: Session, contador_clave: int, mensajes: list[dict]) -> tuple[str, int]:
    working = list(mensajes)
    herramientas = herramientas_disponibles()
    clave_actual = contador_clave
    for _ in range(MAX_RONDAS_HERRAMIENTAS):
        resultado = cerebras_api_service.chat_completion(clave_actual, working, herramientas)
        clave_actual = (clave_actual + 1) % 10
        tool_calls = resultado.get("tool_calls") or []
        if not tool_calls:
            contenido = resultado.get("content")
            return (contenido.strip() if contenido else RESPUESTA_FALLBACK), clave_actual
        working.append(cerebras_api_service.assistant_tool_calls_message(resultado))
        for tc in tool_calls:
            resultado_herramienta = ejecutar_herramienta(tc["name"], tc["arguments"], db)
            working.append(cerebras_api_service.tool_message(tc["id"], resultado_herramienta))
    return RESPUESTA_FALLBACK, clave_actual