from datetime import datetime

from pydantic import BaseModel, Field

from app.rooms.models import Room
from app.game.schemas import GameHistoryResponse, GameResponse, game_history_response, game_response


class CreateRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)


class JoinRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)


class PlayerResponse(BaseModel):
    id: str
    nickname: str
    is_host: bool
    connected: bool
    score: int


class RoomResponse(BaseModel):
    id: str
    code: str
    status: str
    host_player_id: str
    created_at: datetime
    players: list[PlayerResponse]
    selected_mode: str | None
    current_game: GameResponse | None
    cumulative_scores: dict[str, int]
    completed_games: list[GameHistoryResponse]


def room_response(room: Room) -> RoomResponse:
    return RoomResponse(
        id=room.id,
        code=room.code,
        status=room.status.value,
        host_player_id=room.host_player_id,
        created_at=room.created_at,
        players=[
            PlayerResponse(
                id=player.id,
                nickname=player.nickname,
                is_host=player.is_host,
                connected=player.connected,
                score=player.score,
            )
            for player in room.players.values()
        ],
        selected_mode=room.selected_mode,
        current_game=game_response(room.current_game, room.players),
        cumulative_scores=room.cumulative_scores.copy(),
        completed_games=[game_history_response(game) for game in room.completed_games],
    )
