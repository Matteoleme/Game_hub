import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from uuid import uuid4

from app.database import SessionFactory, initialize_database
from app.game.manager import game_manager
from app.game.modes.anecdotes import public_state
from app.main import api
from app.rooms.manager import RoomError, room_manager
from app.rooms.persistence_models import GameRecord, RoomRecord


@pytest.fixture(autouse=True)
async def reset_state() -> None:
    room_manager.rooms.clear()
    room_manager.player_tokens.clear()
    room_manager.closed_codes.clear()
    await initialize_database()


def room_with_three_players():
    room, _ = room_manager.create_room("host", "Host")
    room_manager.join_room(room.code, "Luca")
    room_manager.join_room(room.code, "Anna")
    return room


def test_available_modes_can_be_selected_and_future_modes_are_rejected() -> None:
    room = room_with_three_players()

    game_manager.select_mode(room, "anecdotes")
    assert room.selected_mode == "anecdotes"

    with pytest.raises(RoomError, match="disponibile"):
        game_manager.select_mode(room, "most_likely")


def test_game_has_own_identity_and_returns_room_to_lobby_with_cumulative_scores() -> None:
    room = room_with_three_players()
    room_id = room.id
    player_ids = set(room.players)
    game_manager.select_mode(room, "anecdotes")

    game = game_manager.start_game(room)
    assert game.id != room_id
    assert game.room_id == room_id
    assert game.status == "ACTIVE"
    assert room.current_game is game
    assert room.status == "GAME_RUNNING"

    result = game_manager.finish_game(room)
    assert result.game_id == game.id
    assert room.id == room_id
    assert room.current_game is None
    assert room.status == "LOBBY"
    assert set(room.players) == player_ids
    assert room.cumulative_scores == {player_id: 0 for player_id in player_ids}
    assert all(player.score == 0 for player in room.players.values())


def test_game_requires_three_players() -> None:
    room, _ = room_manager.create_room("host", "Host")
    game_manager.select_mode(room, "anecdotes")

    with pytest.raises(RoomError, match="almeno 3"):
        game_manager.start_game(room)


def test_anecdotes_writing_is_validated_and_advances_after_all_submissions() -> None:
    room = room_with_three_players()
    game_manager.select_mode(room, "anecdotes")
    game_manager.start_game(room)
    player_ids = list(room.players)

    progress = game_manager.submit_anecdote(room, player_ids[0], "  Una storia breve.  ")
    assert progress == {
        "phase": "WRITING",
        "submittedPlayerIds": [player_ids[0]],
        "totalPlayers": 3,
    }

    with pytest.raises(RoomError, match="gia inviato"):
        game_manager.submit_anecdote(room, player_ids[0], "seconda versione")
    with pytest.raises(RoomError, match="da 1 a 500"):
        game_manager.submit_anecdote(room, player_ids[1], " ")
    with pytest.raises(RoomError, match="player non appartiene"):
        game_manager.submit_anecdote(room, "unknown", "test")

    game_manager.submit_anecdote(room, player_ids[1], "Altra storia")
    final_progress = game_manager.submit_anecdote(room, player_ids[2], "Ultima storia")
    assert final_progress["phase"] == "VOTING"
    assert set(final_progress["submittedPlayerIds"]) == set(player_ids)
    assert room.current_game is not None
    assert room.current_game.mode_state["submissions"][player_ids[0]] == "Una storia breve."


def test_anecdotes_voting_is_anonymous_validated_and_advances_stories() -> None:
    room = room_with_three_players()
    game_manager.select_mode(room, "anecdotes")
    game_manager.start_game(room)
    player_ids = list(room.players)
    for index, player_id in enumerate(player_ids):
        game_manager.submit_anecdote(room, player_id, f"Story {index}")

    assert room.current_game is not None
    public = room.current_game.mode_state
    first_story = public["stories"][public["currentStoryIndex"]]
    author_id = first_story["authorPlayerId"]
    voter_ids = [player_id for player_id in player_ids if player_id != author_id]
    target_id = author_id

    with pytest.raises(RoomError, match="votare il tuo"):
        game_manager.submit_vote(room, author_id, target_id)
    with pytest.raises(RoomError, match="votare te stesso"):
        game_manager.submit_vote(room, voter_ids[0], voter_ids[0])
    with pytest.raises(RoomError, match="non appartiene"):
        game_manager.submit_vote(room, voter_ids[0], "unknown")

    progress = game_manager.submit_vote(room, voter_ids[0], target_id)
    assert progress["phase"] == "VOTING"
    assert progress["votesReceived"] == 1
    with pytest.raises(RoomError, match="gia votato"):
        game_manager.submit_vote(room, voter_ids[0], target_id)

    game_manager.submit_vote(room, voter_ids[1], target_id)
    assert room.current_game.mode_state["currentStoryIndex"] == 1

    for story_index in (1, 2):
        story = room.current_game.mode_state["stories"][story_index]
        author = story["authorPlayerId"]
        eligible = [player_id for player_id in player_ids if player_id != author]
        game_manager.submit_vote(room, eligible[0], player_ids[0] if player_ids[0] != eligible[0] else player_ids[1])
        game_manager.submit_vote(room, eligible[1], player_ids[0] if player_ids[0] != eligible[1] else player_ids[1])

    assert room.current_game.phase == "REVEAL"
    reveal_public = public_state(room.current_game)
    assert "authorPlayerId" not in reveal_public
    assert "authorPlayerId" not in reveal_public["currentStory"]


@pytest.mark.asyncio
async def test_api_persists_room_and_game_history() -> None:
    email = f"game-{uuid4()}@example.com"
    password = "password-123"
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as host:
        await host.post("/api/auth/register", json={"email": email, "password": password})
        await host.post("/api/auth/login", json={"email": email, "password": password})
        created = await host.post("/api/rooms", json={"nickname": "Host"})
        code = created.json()["code"]
        async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as guest_one:
            await guest_one.post(f"/api/rooms/{code}/join", json={"nickname": "Luca"})
        async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as guest_two:
            await guest_two.post(f"/api/rooms/{code}/join", json={"nickname": "Anna"})
        await host.post(f"/api/rooms/{code}/mode", json={"mode_id": "anecdotes"})
        started = await host.post(f"/api/rooms/{code}/start")
        game_id = started.json()["current_game"]["id"]
        await host.post(f"/api/rooms/{code}/finish")

    async with SessionFactory() as session:
        room_record = await session.scalar(select(RoomRecord).where(RoomRecord.code == code))
        game_record = await session.scalar(select(GameRecord).where(GameRecord.id == game_id))

    assert room_record is not None
    assert game_record is not None
    assert game_record.finished_at is not None
