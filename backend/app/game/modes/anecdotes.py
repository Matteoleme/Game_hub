from typing import Any
import random
from uuid import uuid4

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
        stories = [
            {"id": str(uuid4()), "authorPlayerId": author_id, "text": story_text, "votes": {}}
            for author_id, story_text in submissions.items()
        ]
        random.SystemRandom().shuffle(stories)
        game.mode_state["stories"] = stories
        game.mode_state["currentStoryIndex"] = 0
        game.phase = "VOTING"
        game.mode_state["phase"] = "VOTING"

    return public_state(game)


def submit_vote(game: Game, voter_id: str, target_player_id: str) -> dict[str, Any]:
    if game.mode != "anecdotes" or game.phase != "VOTING":
        raise ValueError("VOTING_NOT_ACTIVE")
    player_ids: list[str] = game.mode_state["player_ids"]
    if voter_id not in player_ids:
        raise ValueError("PLAYER_NOT_IN_GAME")
    if target_player_id not in player_ids:
        raise ValueError("TARGET_PLAYER_NOT_IN_GAME")

    stories: list[dict[str, Any]] = game.mode_state["stories"]
    current_index: int = game.mode_state["currentStoryIndex"]
    story = stories[current_index]
    if voter_id == story["authorPlayerId"]:
        raise ValueError("AUTHOR_CANNOT_VOTE")
    if voter_id == target_player_id:
        raise ValueError("SELF_VOTE_NOT_ALLOWED")
    votes: dict[str, str] = story["votes"]
    if voter_id in votes:
        raise ValueError("VOTE_ALREADY_SUBMITTED")

    votes[voter_id] = target_player_id
    eligible_voters = len(player_ids) - 1
    if len(votes) == eligible_voters:
        if current_index + 1 < len(stories):
            game.mode_state["currentStoryIndex"] = current_index + 1
        else:
            game.phase = "REVEAL"
            game.mode_state["phase"] = "REVEAL"
    return public_state(game)


def calculate_points(game: Game) -> dict[str, int]:
    points = {player_id: 0 for player_id in game.mode_state["player_ids"]}
    for story in game.mode_state["stories"]:
        for voter_id, target_id in story["votes"].items():
            if target_id == story["authorPlayerId"]:
                points[voter_id] += 1
    return points


def public_state(game: Game, players: dict[str, Any] | None = None) -> dict[str, Any]:
    submissions: dict[str, str] = game.mode_state["submissions"]
    state: dict[str, Any] = {
        "phase": game.phase,
        "submittedPlayerIds": list(submissions),
        "totalPlayers": len(game.mode_state["player_ids"]),
    }
    if game.phase not in {"VOTING", "REVEAL"}:
        return state

    stories: list[dict[str, Any]] = game.mode_state["stories"]
    story = stories[game.mode_state["currentStoryIndex"]]
    state.update(
        {
            "currentStory": {"id": story["id"], "text": story["text"]},
            "currentStoryIndex": game.mode_state["currentStoryIndex"],
            "totalStories": len(stories),
            "votesReceived": len(story["votes"]),
            "eligibleVotes": len(game.mode_state["player_ids"]) - 1,
        }
    )
    if game.phase == "REVEAL":
        reveal_stories = []
        for reveal_story in stories:
            reveal_votes = []
            for voter_id, target_id in reveal_story["votes"].items():
                correct_vote = target_id == reveal_story["authorPlayerId"]
                reveal_votes.append(
                    {
                        "voterPlayerId": voter_id,
                        "voterNickname": players[voter_id].nickname if players and voter_id in players else voter_id,
                        "targetPlayerId": target_id,
                        "targetNickname": players[target_id].nickname if players and target_id in players else target_id,
                        "correct": correct_vote,
                        "pointsEarned": 1 if correct_vote else 0,
                    }
                )
            reveal_stories.append(
                {
                    "id": reveal_story["id"],
                    "text": reveal_story["text"],
                    "authorPlayerId": reveal_story["authorPlayerId"],
                    "authorNickname": players[reveal_story["authorPlayerId"]].nickname
                    if players and reveal_story["authorPlayerId"] in players
                    else reveal_story["authorPlayerId"],
                    "votes": reveal_votes,
                }
            )
        state["revealStories"] = reveal_stories
        state["pointsByPlayer"] = game.mode_state.get("pointsByPlayer", {})
    return state
