from datetime import datetime

from pydantic import BaseModel

from app.game.models import Game
from app.game.modes.anecdotes import public_state
from app.game.modes.registry import ModeDescriptor
from app.rooms.models import Room


class SelectModeRequest(BaseModel):
    mode_id: str


class GameResponse(BaseModel):
    id: str
    room_id: str
    mode: str
    status: str
    phase: str
    started_at: datetime
    finished_at: datetime | None
    mode_state: dict


class GameModeResponse(BaseModel):
    id: str
    name: str
    available: bool


class GameHistoryResponse(BaseModel):
    id: str
    room_id: str
    mode: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    points_by_player: dict[str, int]


def game_response(game: Game | None, players: dict | None = None) -> GameResponse | None:
    if game is None:
        return None
    return GameResponse(
        id=game.id,
        room_id=game.room_id,
        mode=game.mode,
        status=game.status.value,
        phase=game.phase,
        started_at=game.started_at,
        finished_at=game.finished_at,
        mode_state=public_state(game, players) if game.mode == "anecdotes" else {},
    )


def mode_response(mode: ModeDescriptor) -> GameModeResponse:
    return GameModeResponse(id=mode.id, name=mode.name, available=mode.available)


def game_history_response(game: Game) -> GameHistoryResponse:
    return GameHistoryResponse(
        id=game.id,
        room_id=game.room_id,
        mode=game.mode,
        status=game.status.value,
        started_at=game.started_at,
        finished_at=game.finished_at,
        points_by_player=game.mode_state.get("pointsByPlayer", {}),
    )
