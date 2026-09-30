from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from app.game.models import Game


class RoomStatus(StrEnum):
    LOBBY = "LOBBY"
    GAME_RUNNING = "GAME_RUNNING"
    GAME_FINISHED = "GAME_FINISHED"
    CLOSED = "CLOSED"


@dataclass
class Player:
    id: str
    nickname: str
    is_host: bool
    user_id: str | None = None
    connected: bool = False
    score: int = 0
    socket_id: str | None = None


@dataclass
class Room:
    id: str
    code: str
    host_user_id: str
    host_player_id: str
    status: RoomStatus = RoomStatus.LOBBY
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    players: dict[str, Player] = field(default_factory=dict)
    selected_mode: str | None = None
    current_game: Game | None = None
    completed_games: list[Game] = field(default_factory=list)
    cumulative_scores: dict[str, int] = field(default_factory=dict)
