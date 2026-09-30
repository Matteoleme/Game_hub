from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class GameStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"


@dataclass
class Game:
    id: str
    room_id: str
    mode: str
    status: GameStatus = GameStatus.ACTIVE
    phase: str = "ACTIVE"
    mode_state: dict = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


@dataclass
class GameResult:
    game_id: str
    points_by_player: dict[str, int]
    finished_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
