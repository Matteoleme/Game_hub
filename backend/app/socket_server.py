import socketio

from app.config import get_settings


settings = get_settings()
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[settings.frontend_origin],
)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    await sio.emit("system:connected", {"connectionId": sid}, to=sid)


@sio.event
async def disconnect(sid: str) -> None:
    return None
