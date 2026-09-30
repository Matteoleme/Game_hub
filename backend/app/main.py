from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.game_modes import router as game_modes_router
from app.api.rooms import router as rooms_router
from app.config import get_settings
from app.database import initialize_database
from app.socket_server import sio


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield


api = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api.include_router(health_router, prefix="/api")
api.include_router(game_modes_router, prefix="/api")
api.include_router(auth_router, prefix="/api")
api.include_router(rooms_router, prefix="/api")

static_directory = Path(__file__).parent.parent / "static"
if static_directory.is_dir():
    api.mount("/", StaticFiles(directory=static_directory, html=True), name="frontend")

app = socketio.ASGIApp(sio, other_asgi_app=api)
