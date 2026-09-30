from uuid import uuid4

from app.game.models import Game, GameResult, GameStatus
from app.game.modes.registry import get_mode
from app.rooms.models import Room, RoomStatus
from app.rooms.manager import MIN_PLAYERS, RoomError


class GameManager:
    def select_mode(self, room: Room, mode_id: str) -> None:
        if room.status != RoomStatus.LOBBY:
            raise RoomError("ROOM_NOT_IN_LOBBY", "La modalita puo essere scelta solo nella lobby.")
        try:
            get_mode(mode_id)
        except ValueError as error:
            raise RoomError("GAME_MODE_UNAVAILABLE", "Questa modalita non e' disponibile.") from error
        room.selected_mode = mode_id

    def start_game(self, room: Room) -> Game:
        if room.status != RoomStatus.LOBBY:
            raise RoomError("GAME_ALREADY_ACTIVE", "Una partita e' gia attiva.")
        if len(room.players) < MIN_PLAYERS:
            raise RoomError("MINIMUM_PLAYERS_REQUIRED", "Servono almeno 3 giocatori per iniziare.")
        if room.selected_mode is None:
            raise RoomError("GAME_MODE_REQUIRED", "Seleziona una modalita prima di iniziare.")

        mode = get_mode(room.selected_mode)
        game = Game(
            id=str(uuid4()),
            room_id=room.id,
            mode=mode.id,
            mode_state=mode.create_initial_state(list(room.players)),
        )
        room.current_game = game
        room.status = RoomStatus.GAME_RUNNING
        return game

    def finish_game(self, room: Room) -> GameResult:
        game = room.current_game
        if room.status != RoomStatus.GAME_RUNNING or game is None:
            raise RoomError("NO_ACTIVE_GAME", "Non c'e' una partita attiva.")

        result = GameResult(game_id=game.id, points_by_player={player_id: 0 for player_id in room.players})
        game.status = GameStatus.FINISHED
        game.phase = "FINISHED"
        game.finished_at = result.finished_at
        for player_id, points in result.points_by_player.items():
            room.cumulative_scores[player_id] = room.cumulative_scores.get(player_id, 0) + points
            if player_id in room.players:
                room.players[player_id].score = room.cumulative_scores[player_id]
        room.completed_games.append(game)
        room.current_game = None
        room.selected_mode = None
        room.status = RoomStatus.LOBBY
        return result


game_manager = GameManager()
