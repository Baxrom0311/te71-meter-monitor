import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.security import validate_access_token
from services.websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    # Token ni query param yoki subprotocol orqali qabul qilamiz
    token = ws.query_params.get("token")
    if not token:
        # Subprotocol orqali ham token yuborish mumkin
        protocols = ws.headers.get("sec-websocket-protocol", "")
        parts = [p.strip() for p in protocols.split(",") if p.strip()]
        token = parts[0] if parts else None

    if not token:
        await ws.close(code=1008, reason="Token kerak")
        return

    try:
        payload = await validate_access_token(token)
    except Exception:
        await ws.close(code=1008, reason="Token noto'g'ri yoki muddati tugagan")
        return

    await ws_manager.connect(ws)
    logger.info("WebSocket connected: user=%s", payload.get("username"))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
        logger.info("WebSocket disconnected: user=%s", payload.get("username"))
