from abc import ABC, abstractmethod


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
        return {"player_ids": player_ids}
