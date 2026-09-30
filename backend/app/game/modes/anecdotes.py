from typing import Any

from app.game.models import Game

MAX_STORY_LENGTH = 500
MIN_STORY_LENGTH = 1


def create_state(player_ids: list[str]) -> dict[str, Any]:
    return {
        "player_ids": player_ids,
        "submissions": {},
        "phase": "WRITING",
    }


def submit_story(game: Game, player_id: str, text: str) -> dict[str, Any]:
    if game.mode != "anecdotes" or game.phase != "WRITING":
        raise ValueError("WRITING_NOT_ACTIVE")
    if player_id not in game.mode_state["player_ids"]:
        raise ValueError("PLAYER_NOT_IN_GAME")

    normalized_text = text.strip()
    if not MIN_STORY_LENGTH <= len(normalized_text) <= MAX_STORY_LENGTH:
        raise ValueError("STORY_LENGTH_INVALID")

    submissions: dict[str, str] = game.mode_state["submissions"]
    if player_id in submissions:
        raise ValueError("STORY_ALREADY_SUBMITTED")

    submissions[player_id] = normalized_text
    submitted_ids = list(submissions)
    if len(submissions) == len(game.mode_state["player_ids"]):
        game.phase = "VOTING"
        game.mode_state["phase"] = "VOTING"

    return public_state(game)


def public_state(game: Game) -> dict[str, Any]:
    submissions: dict[str, str] = game.mode_state["submissions"]
    return {
        "phase": game.phase,
        "submittedPlayerIds": list(submissions),
        "totalPlayers": len(game.mode_state["player_ids"]),
    }
