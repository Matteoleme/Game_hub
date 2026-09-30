from uuid import uuid4

from app.game.models import Game, GameResult, GameStatus
from app.game.modes.anecdotes import calculate_points, public_state, submit_story, submit_vote
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
        game.phase = game.mode_state.get("phase", game.phase)
        room.current_game = game
        room.status = RoomStatus.GAME_RUNNING
        return game

    def finish_game(self, room: Room) -> GameResult:
        game = room.current_game
        if room.status != RoomStatus.GAME_RUNNING or game is None:
            raise RoomError("NO_ACTIVE_GAME", "Non c'e' una partita attiva.")

        points_by_player = game.mode_state.get("pointsByPlayer", {player_id: 0 for player_id in room.players})
        result = GameResult(game_id=game.id, points_by_player=points_by_player)
        game.status = GameStatus.FINISHED
        game.phase = "FINISHED"
        game.finished_at = result.finished_at
        if not game.mode_state.get("scoreApplied", False):
            for player_id, points in result.points_by_player.items():
                room.cumulative_scores[player_id] = room.cumulative_scores.get(player_id, 0) + points
                if player_id in room.players:
                    room.players[player_id].score = room.cumulative_scores[player_id]
        room.completed_games.append(game)
        room.current_game = None
        room.selected_mode = None
        room.status = RoomStatus.LOBBY
        return result

    def submit_anecdote(self, room: Room, player_id: str, text: str) -> dict:
        game = room.current_game
        if room.status != RoomStatus.GAME_RUNNING or game is None:
            raise RoomError("NO_ACTIVE_GAME", "Non c'e' una partita attiva.")
        try:
            return submit_story(game, player_id, text)
        except ValueError as error:
            messages = {
                "WRITING_NOT_ACTIVE": "La fase di scrittura non e' attiva.",
                "PLAYER_NOT_IN_GAME": "Il player non appartiene a questa partita.",
                "STORY_LENGTH_INVALID": "L'aneddoto deve contenere da 1 a 500 caratteri.",
                "STORY_ALREADY_SUBMITTED": "Hai gia inviato il tuo aneddoto.",
            }
            raise RoomError(str(error), messages.get(str(error), "Aneddoto non valido.")) from error

    def submit_vote(self, room: Room, player_id: str, target_player_id: str) -> dict:
        game = room.current_game
        if room.status != RoomStatus.GAME_RUNNING or game is None:
            raise RoomError("NO_ACTIVE_GAME", "Non c'e' una partita attiva.")
        try:
            progress = submit_vote(game, player_id, target_player_id)
            if game.phase == "REVEAL" and not game.mode_state.get("scoreApplied", False):
                points = calculate_points(game)
                game.mode_state["pointsByPlayer"] = points
                game.mode_state["scoreApplied"] = True
                for scored_player_id, scored_points in points.items():
                    room.cumulative_scores[scored_player_id] = room.cumulative_scores.get(scored_player_id, 0) + scored_points
                    if scored_player_id in room.players:
                        room.players[scored_player_id].score = room.cumulative_scores[scored_player_id]
                return public_state(game, room.players)
            return progress
        except ValueError as error:
            messages = {
                "VOTING_NOT_ACTIVE": "La fase di votazione non e' attiva.",
                "PLAYER_NOT_IN_GAME": "Il player non appartiene a questa partita.",
                "TARGET_PLAYER_NOT_IN_GAME": "Il player votato non appartiene alla partita.",
                "SELF_VOTE_NOT_ALLOWED": "Non puoi votare te stesso.",
                "AUTHOR_CANNOT_VOTE": "Non puoi votare il tuo stesso aneddoto.",
                "VOTE_ALREADY_SUBMITTED": "Hai gia votato questo aneddoto.",
            }
            raise RoomError(str(error), messages.get(str(error), "Voto non valido.")) from error


game_manager = GameManager()
