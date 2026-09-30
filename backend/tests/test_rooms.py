from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import initialize_database
from app.main import api
from app.rooms.manager import MAX_PLAYERS, RoomError, room_manager


@pytest.fixture(autouse=True)
async def reset_rooms() -> None:
    room_manager.rooms.clear()
    room_manager.player_tokens.clear()
    room_manager.closed_codes.clear()
    await initialize_database()


async def register_and_login(client: AsyncClient) -> None:
    email = f"host-{uuid4()}@example.com"
    await client.post("/api/auth/register", json={"email": email, "password": "password-123"})
    response = await client.post("/api/auth/login", json={"email": email, "password": "password-123"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_and_join_room_enforces_unique_nickname() -> None:
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as host:
        await register_and_login(host)
        created = await host.post("/api/rooms", json={"nickname": "Mario"})
        code = created.json()["code"]

    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as guest:
        joined = await guest.post(f"/api/rooms/{code.lower()}/join", json={"nickname": "Luca"})
        duplicate = await guest.post(f"/api/rooms/{code}/join", json={"nickname": "mArIo"})

    assert created.status_code == 201
    assert joined.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "NICKNAME_ALREADY_EXISTS"
    assert len(joined.json()["players"]) == 2
    refreshed = await guest.get(f"/api/rooms/{code}")
    assert refreshed.status_code == 200
    assert refreshed.json()["code"] == code
    assert {player["nickname"] for player in refreshed.json()["players"]} == {"Mario", "Luca"}


@pytest.mark.asyncio
async def test_room_has_maximum_of_twenty_players() -> None:
    room, _ = room_manager.create_room("host", "Host")
    for index in range(MAX_PLAYERS - 1):
        room_manager.join_room(room.code, f"Player {index}")

    with pytest.raises(RoomError, match="limite"):
        room_manager.join_room(room.code, "One too many")

    assert len(room.players) == MAX_PLAYERS


@pytest.mark.asyncio
async def test_only_host_can_close_room_and_room_stays_after_disconnect() -> None:
    room, host_token = room_manager.create_room("host", "Host")
    room_manager.join_room(room.code, "Guest")
    room_manager.connect_player(host_token, "socket-1")
    disconnected = room_manager.disconnect_socket("socket-1")

    assert disconnected is not None
    assert room_manager.get_room(room.code).players[room.host_player_id].connected is False

    with pytest.raises(RoomError, match="Solo l'host"):
        room_manager.close_room("another-user", room.code)

    closed = room_manager.close_room("host", room.code)
    assert closed.status == "CLOSED"
    with pytest.raises(RoomError, match="chiusa"):
        room_manager.get_room(room.code)


def test_reconnection_keeps_player_and_ignores_stale_socket_disconnect() -> None:
    room, token = room_manager.create_room("host", "Host")
    first_connection = room_manager.connect_player(token, "socket-old")
    second_connection = room_manager.connect_player(token, "socket-new")

    assert first_connection is not None
    assert second_connection is not None
    assert room.players[room.host_player_id].connected is True
    assert room.players[room.host_player_id].socket_id == "socket-new"
    assert room_manager.disconnect_socket("socket-old") is None
    assert room.players[room.host_player_id].connected is True
    assert room.players[room.host_player_id].socket_id == "socket-new"

    disconnected = room_manager.disconnect_socket("socket-new")
    assert disconnected is not None
    assert room.players[room.host_player_id].connected is False
    assert room.players[room.host_player_id].socket_id is None
