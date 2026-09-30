from dataclasses import dataclass

from app.game.modes.base import AnecdotesMode, GameMode


@dataclass(frozen=True)
class ModeDescriptor:
    id: str
    name: str
    available: bool


_MODE_DESCRIPTORS = (
    ModeDescriptor(id="anecdotes", name="Aneddoti", available=True),
    ModeDescriptor(id="two_truths_one_lie", name="Due verita e una bugia", available=False),
    ModeDescriptor(id="most_likely", name="Most Likely", available=False),
)
_MODES: dict[str, GameMode] = {"anecdotes": AnecdotesMode()}


def list_modes() -> tuple[ModeDescriptor, ...]:
    return _MODE_DESCRIPTORS


def get_mode(mode_id: str) -> GameMode:
    mode = _MODES.get(mode_id)
    if mode is None:
        raise ValueError("GAME_MODE_UNAVAILABLE")
    return mode
