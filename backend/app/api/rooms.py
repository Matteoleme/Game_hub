from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user
from app.auth.models import User
from app.database import get_session
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


def room_error(error: RoomError) -> HTTPException:
    code_to_status = {
        "ROOM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "ROOM_CLOSED": status.HTTP_410_GONE,
        "NICKNAME_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
        "ROOM_FULL": status.HTTP_409_CONFLICT,
        "HOST_PERMISSION_REQUIRED": status.HTTP_403_FORBIDDEN,
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
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room, token = room_manager.create_room(user.id, payload.nickname)
    except RoomError as error:
        raise room_error(error) from error
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
    user: Annotated[User, Depends(current_user)],
) -> RoomResponse:
    try:
        room = room_manager.close_room(user.id, code)
    except RoomError as error:
        raise room_error(error) from error
    from app.socket_server import sio

    await sio.emit("room:closed", room_response(room).model_dump(mode="json"), room=room.code)
    return room_response(room)
