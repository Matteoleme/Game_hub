from fastapi import APIRouter

from app.game.modes.registry import list_modes
from app.game.schemas import GameModeResponse, mode_response

router = APIRouter(prefix="/game-modes", tags=["game"])


@router.get("", response_model=list[GameModeResponse])
async def game_modes() -> list[GameModeResponse]:
    return [mode_response(mode) for mode in list_modes()]
