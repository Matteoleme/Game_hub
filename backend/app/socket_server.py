import socketio
from http.cookies import SimpleCookie
from typing import Any

from app.config import get_settings
from app.database import SessionFactory
from app.game.manager import game_manager
from app.game.persistence import persist_game_finished, persist_game_started
from app.rooms.manager import RoomError, room_manager
from app.rooms.schemas import room_response


settings = get_settings()
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[settings.frontend_origin],
)
socket_tokens: dict[str, str] = {}


def room_payload(room: Any) -> dict[str, Any]:
    return room_response(room).model_dump(mode="json")


def cookie_token(environ: dict[str, Any]) -> str | None:
    cookies = SimpleCookie(environ.get("HTTP_COOKIE", ""))
    token = cookies.get("game_hub_player")
    return token.value if token else None


async def emit_room_error(sid: str, error: RoomError | None = None) -> None:
    if error is None:
        await sio.emit(
            "error",
            {"code": "PLAYER_SESSION_INVALID", "message": "Sessione giocatore non valida."},
            to=sid,
        )
        return
    await sio.emit("error", {"code": error.code, "message": error.message}, to=sid)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    token = (auth or {}).get("playerToken") or cookie_token(environ)
    result = room_manager.connect_player(token, sid)
    if result is None:
        await sio.emit("system:connected", {"connectionId": sid}, to=sid)
        return
    room, player = result
    socket_tokens[sid] = token
    await sio.enter_room(sid, room.code)
    await sio.emit("room:updated", room_payload(room), to=sid)
    await sio.emit("player:connected", {"playerId": player.id}, room=room.code, skip_sid=sid)


@sio.event
async def disconnect(sid: str) -> None:
    socket_tokens.pop(sid, None)
    result = room_manager.disconnect_socket(sid)
    if result is not None:
        room, player = result
        await sio.emit(
            "player:disconnected",
            {"playerId": player.id},
            room=room.code,
        )
        await sio.emit("room:updated", room_payload(room), room=room.code)


@sio.on("room:join")
async def room_join(sid: str, data: dict[str, Any] | None = None) -> None:
    token = (data or {}).get("playerToken") or socket_tokens.get(sid)
    result = room_manager.connect_player(token, sid)
    if result is None:
        await emit_room_error(sid)
        return
    room, player = result
    socket_tokens[sid] = token
    await sio.enter_room(sid, room.code)
    await sio.emit("room:updated", room_payload(room), to=sid)
    await sio.emit("player:connected", {"playerId": player.id}, room=room.code, skip_sid=sid)


@sio.on("room:leave")
async def room_leave(sid: str) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None:
        await emit_room_error(sid)
        return
    room = result[0]
    try:
        room_manager.leave_room(token)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    socket_tokens.pop(sid, None)
    await sio.emit("room:updated", room_payload(room), room=room.code)
    await sio.leave_room(sid, room.code)


@sio.on("room:close")
async def room_close(sid: str) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None or not result[1].is_host or result[1].user_id is None:
        await emit_room_error(sid, RoomError("HOST_PERMISSION_REQUIRED", "Solo l'host puo chiudere la stanza."))
        return
    room = result[0]
    try:
        closed_room = room_manager.close_room(result[1].user_id, room.code)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    await sio.emit("room:closed", room_payload(closed_room), room=room.code)


@sio.on("room:select_mode")
async def room_select_mode(sid: str, data: dict[str, Any] | None = None) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None or not result[1].is_host:
        await emit_room_error(sid, RoomError("HOST_PERMISSION_REQUIRED", "Solo l'host puo scegliere la modalita."))
        return
    mode_id = (data or {}).get("modeId")
    if not isinstance(mode_id, str):
        await emit_room_error(sid, RoomError("GAME_MODE_UNAVAILABLE", "Modalita non valida."))
        return
    room = result[0]
    try:
        game_manager.select_mode(room, mode_id)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    await sio.emit("room:updated", room_payload(room), room=room.code)


@sio.on("game:start")
async def game_start(sid: str) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None or not result[1].is_host:
        await emit_room_error(sid, RoomError("HOST_PERMISSION_REQUIRED", "Solo l'host puo iniziare la partita."))
        return
    room = result[0]
    try:
        game = game_manager.start_game(room)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    async with SessionFactory() as session:
        await persist_game_started(session, game)
    await sio.emit("game:started", room_payload(room), room=room.code)


@sio.on("game:finish")
async def game_finish(sid: str) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None or not result[1].is_host:
        await emit_room_error(sid, RoomError("HOST_PERMISSION_REQUIRED", "Solo l'host puo terminare la partita."))
        return
    room = result[0]
    try:
        game_result = game_manager.finish_game(room)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    finished_game = next(game for game in room.completed_games if game.id == game_result.game_id)
    async with SessionFactory() as session:
        await persist_game_finished(session, finished_game)
    await sio.emit("game:finished", room_payload(room), room=room.code)


@sio.on("story:submit")
async def story_submit(sid: str, data: dict[str, Any] | None = None) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None:
        await emit_room_error(sid)
        return
    text = (data or {}).get("text")
    if not isinstance(text, str):
        await emit_room_error(sid, RoomError("STORY_LENGTH_INVALID", "L'aneddoto deve contenere da 1 a 500 caratteri."))
        return
    room, player = result
    try:
        game_manager.submit_anecdote(room, player.id, text)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    await sio.emit("writing:updated", room_payload(room), room=room.code)


@sio.on("vote:submit")
async def vote_submit(sid: str, data: dict[str, Any] | None = None) -> None:
    token = socket_tokens.get(sid)
    result = room_manager.get_room_for_player_token(token)
    if result is None:
        await emit_room_error(sid)
        return
    target_player_id = (data or {}).get("targetPlayerId")
    if not isinstance(target_player_id, str):
        await emit_room_error(sid, RoomError("TARGET_PLAYER_NOT_IN_GAME", "Player votato non valido."))
        return
    room, player = result
    try:
        game_manager.submit_vote(room, player.id, target_player_id)
    except RoomError as error:
        await emit_room_error(sid, error)
        return
    await sio.emit("voting:updated", room_payload(room), room=room.code)
