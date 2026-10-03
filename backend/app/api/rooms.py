from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user
from app.auth.models import User
from app.database import get_session
from app.game.manager import game_manager
from app.game.persistence import (
    persist_game_finished,
    persist_game_result,
    persist_game_started,
    persist_room,
    persist_room_closed,
)
from app.game.schemas import GameHistoryResponse, SelectModeRequest, game_history_response
from pydantic import Field
from pydantic import BaseModel
from app.rooms.manager import RoomError, room_manager
from app.rooms.schemas import (
    CreateRoomRequest,
    JoinRoomRequest,
    RoomResponse,
    room_response,
)

router = APIRouter(prefix="/rooms", tags=["rooms"])
PLAYER_COOKIE_NAME = "game_hub_player"
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class StorySubmissionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class VoteSubmissionRequest(BaseModel):
    target_player_id: str


def room_error(error: RoomError) -> HTTPException:
    code_to_status = {
        "ROOM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "ROOM_CLOSED": status.HTTP_410_GONE,
        "NICKNAME_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
        "ROOM_FULL": status.HTTP_409_CONFLICT,
        "HOST_PERMISSION_REQUIRED": status.HTTP_403_FORBIDDEN,
        "MINIMUM_PLAYERS_REQUIRED": status.HTTP_409_CONFLICT,
        "GAME_MODE_REQUIRED": status.HTTP_409_CONFLICT,
        "GAME_MODE_UNAVAILABLE": status.HTTP_400_BAD_REQUEST,
        "GAME_ALREADY_ACTIVE": status.HTTP_409_CONFLICT,
        "NO_ACTIVE_GAME": status.HTTP_409_CONFLICT,
        "ROOM_NOT_IN_LOBBY": status.HTTP_409_CONFLICT,
        "AUTHOR_CANNOT_VOTE": status.HTTP_409_CONFLICT,
        "SELF_VOTE_NOT_ALLOWED": status.HTTP_409_CONFLICT,
        "VOTE_ALREADY_SUBMITTED": status.HTTP_409_CONFLICT,
        "TARGET_PLAYER_NOT_IN_GAME": status.HTTP_400_BAD_REQUEST,
        "VOTING_NOT_ACTIVE": status.HTTP_409_CONFLICT,
        "GAME_NOT_READY_TO_FINISH": status.HTTP_409_CONFLICT,
    }
    return HTTPException(
        status_code=code_to_status.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": error.code, "message": error.message},
    )


def set_player_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=PLAYER_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: CreateRoomRequest,
    response: Response,
    session: SessionDependency,
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room, token = room_manager.create_room(user.id, payload.nickname)
    except RoomError as error:
        raise room_error(error) from error
    await persist_room(session, room)
    set_player_cookie(response, token)
    return room_response(room)


@router.post("/{code}/join", response_model=RoomResponse)
async def join_room(
    code: str,
    payload: JoinRoomRequest,
    response: Response,
) -> RoomResponse:
    try:
        room, _, token = room_manager.join_room(code, payload.nickname)
    except RoomError as error:
        raise room_error(error) from error
    set_player_cookie(response, token)
    from app.socket_server import emit_room_update

    await emit_room_update(room, room_code=room.code)
    return room_response(room)


@router.get("/{code}", response_model=RoomResponse)
async def get_room(
    code: str,
    session: SessionDependency,
    player_token: str | None = Cookie(default=None, alias=PLAYER_COOKIE_NAME),
) -> RoomResponse:
    player_result = room_manager.get_room_for_player_token(player_token)
    if player_result is not None:
        room, _ = player_result
        if room.code == code.strip().upper():
            return room_response(room)
    try:
        room = room_manager.get_room(code)
    except RoomError as error:
        raise room_error(error) from error
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "ROOM_ACCESS_REQUIRED", "message": "Accedi alla stanza con il relativo token."},
    )


@router.get("/{code}/history", response_model=list[GameHistoryResponse])
async def room_history(
    code: str,
    player_token: str | None = Cookie(default=None, alias=PLAYER_COOKIE_NAME),
) -> list[GameHistoryResponse]:
    player_result = room_manager.get_room_for_player_token(player_token)
    if player_result is None or player_result[0].code != code.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROOM_ACCESS_REQUIRED", "message": "Accesso alla stanza richiesto."},
        )
    return [game_history_response(game) for game in player_result[0].completed_games]


@router.post("/{code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(
    code: str,
    response: Response,
    player_token: str | None = Cookie(default=None, alias=PLAYER_COOKIE_NAME),
) -> None:
    result = room_manager.get_room_for_player_token(player_token)
    if result is None or result[0].code != code.strip().upper():
        raise HTTPException(status_code=403, detail={"code": "ROOM_ACCESS_REQUIRED", "message": "Accesso alla stanza richiesto."})
    try:
        room_manager.leave_room(player_token)
    except RoomError as error:
        raise room_error(error) from error
    response.delete_cookie(PLAYER_COOKIE_NAME)


@router.post("/{code}/close", response_model=RoomResponse)
async def close_room(
    code: str,
    session: SessionDependency,
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room = room_manager.close_room(user.id, code)
    except RoomError as error:
        raise room_error(error) from error
    await persist_room_closed(session, room)
    from app.socket_server import sio

    await sio.emit("room:closed", room_response(room).model_dump(mode="json"), room=room.code)
    return room_response(room)


@router.post("/{code}/mode", response_model=RoomResponse)
async def select_mode(
    code: str,
    payload: SelectModeRequest,
    session: SessionDependency,
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room, _ = room_manager.get_host_room(code, user.id)
        game_manager.select_mode(room, payload.mode_id)
    except RoomError as error:
        raise room_error(error) from error
    from app.socket_server import emit_room_update

    await emit_room_update(room, room_code=room.code)
    return room_response(room)


@router.post("/{code}/start", response_model=RoomResponse)
async def start_game(
    code: str,
    session: SessionDependency,
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room, _ = room_manager.get_host_room(code, user.id)
        game = game_manager.start_game(room)
    except (RoomError, ValueError) as error:
        if isinstance(error, RoomError):
            raise room_error(error) from error
        raise room_error(RoomError("GAME_MODE_UNAVAILABLE", "Questa modalita non e' disponibile.")) from error
    await persist_game_started(session, game)
    from app.socket_server import emit_room_update

    await emit_room_update(room, room_code=room.code, legacy_events=("game:started",))
    return room_response(room)


@router.post("/{code}/finish", response_model=RoomResponse)
async def finish_game(
    code: str,
    session: SessionDependency,
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room, _ = room_manager.get_host_room(code, user.id)
        result = game_manager.finish_game(room)
    except RoomError as error:
        raise room_error(error) from error
    finished_game = next(game for game in room.completed_games if game.id == result.game_id)
    await persist_game_finished(session, finished_game)
    await persist_game_result(session, result)
    from app.socket_server import emit_room_update

    await emit_room_update(room, room_code=room.code, legacy_events=("game:finished",))
    return room_response(room)


@router.post("/{code}/story", response_model=RoomResponse)
async def submit_story(
    code: str,
    payload: StorySubmissionRequest,
    player_token: str | None = Cookie(default=None, alias=PLAYER_COOKIE_NAME),
) -> RoomResponse:
    player_result = room_manager.get_room_for_player_token(player_token)
    if player_result is None or player_result[0].code != code.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROOM_ACCESS_REQUIRED", "message": "Accesso alla stanza richiesto."},
        )
    room, player = player_result
    try:
        game_manager.submit_anecdote(room, player.id, payload.text)
    except RoomError as error:
        raise room_error(error) from error
    from app.socket_server import emit_room_update

    await emit_room_update(room, room_code=room.code, legacy_events=("writing:updated",))
    return room_response(room)


@router.post("/{code}/vote", response_model=RoomResponse)
async def submit_vote(
    code: str,
    payload: VoteSubmissionRequest,
    player_token: str | None = Cookie(default=None, alias=PLAYER_COOKIE_NAME),
) -> RoomResponse:
    player_result = room_manager.get_room_for_player_token(player_token)
    if player_result is None or player_result[0].code != code.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROOM_ACCESS_REQUIRED", "message": "Accesso alla stanza richiesto."},
        )
    room, player = player_result
    try:
        game_manager.submit_vote(room, player.id, payload.target_player_id)
    except RoomError as error:
        raise room_error(error) from error
    from app.socket_server import emit_room_update

    await emit_room_update(room, room_code=room.code, legacy_events=("voting:updated",))
    return room_response(room)
