from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class MensajeRequest(BaseModel):
    sessionId: str | None = None
    message: str


def _requerir_cliente(x_client_id: str | None) -> str:
    if not x_client_id:
        raise HTTPException(status_code=400, detail="Falta el encabezado X-Client-Id")
    return x_client_id


@router.get("/sesion")
def sesion_activa(x_client_id: str | None = Header(None, alias="X-Client-Id"), db: Session = Depends(get_db)):
    cliente_id = _requerir_cliente(x_client_id)
    return chat_service.obtener_sesion_ui(db, cliente_id)


@router.post("/nueva-sesion")
def nueva_sesion(x_client_id: str | None = Header(None, alias="X-Client-Id"), db: Session = Depends(get_db)):
    cliente_id = _requerir_cliente(x_client_id)
    return chat_service.nueva_sesion_ui(db, cliente_id)


@router.get("/sesiones")
def sesiones(x_client_id: str | None = Header(None, alias="X-Client-Id"), db: Session = Depends(get_db)):
    cliente_id = _requerir_cliente(x_client_id)
    return chat_service.listar_sesiones_ui(db, cliente_id)


@router.get("/sesiones/{session_id}")
def sesion_por_id(session_id: str, x_client_id: str | None = Header(None, alias="X-Client-Id"), db: Session = Depends(get_db)):
    cliente_id = _requerir_cliente(x_client_id)
    try:
        return chat_service.obtener_sesion_por_id_ui(db, cliente_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/mensaje")
def mensaje(body: MensajeRequest, x_client_id: str | None = Header(None, alias="X-Client-Id"), db: Session = Depends(get_db)):
    cliente_id = _requerir_cliente(x_client_id)
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio")
    return chat_service.enviar_mensaje(db, cliente_id, body.sessionId, body.message)