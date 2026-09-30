from abc import ABC, abstractmethod

from app.game.modes.anecdotes import create_state


class GameMode(ABC):
    id: str
    name: str

    @abstractmethod
    def create_initial_state(self, player_ids: list[str]) -> dict:
        raise NotImplementedError


class AnecdotesMode(GameMode):
    id = "anecdotes"
    name = "Aneddoti"

    def create_initial_state(self, player_ids: list[str]) -> dict:
        return create_state(player_ids)
