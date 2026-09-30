import hashlib
import secrets
import string
from uuid import uuid4

from app.rooms.models import Player, Room, RoomStatus

MIN_PLAYERS = 3
MAX_PLAYERS = 20
NICKNAME_MIN_LENGTH = 1
NICKNAME_MAX_LENGTH = 24


class RoomError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.player_tokens: dict[str, tuple[str, str]] = {}
        self.closed_codes: set[str] = set()

    def create_room(self, host_user_id: str, nickname: str) -> tuple[Room, str]:
        normalized_nickname = self._validate_nickname(nickname)
        code = self._new_code()
        host_player = Player(
            id=str(uuid4()),
            nickname=normalized_nickname,
            is_host=True,
            user_id=host_user_id,
            connected=True,
        )
        room = Room(
            id=str(uuid4()),
            code=code,
            host_user_id=host_user_id,
            host_player_id=host_player.id,
            players={host_player.id: host_player},
        )
        self.rooms[code] = room
        token = self._register_player_token(room, host_player)
        return room, token

    def join_room(self, code: str, nickname: str) -> tuple[Room, Player, str]:
        room = self.get_room(code)
        if room.status != RoomStatus.LOBBY:
            raise RoomError("ROOM_NOT_JOINABLE", "Questa stanza non accetta nuovi giocatori.")
        if len(room.players) >= MAX_PLAYERS:
            raise RoomError("ROOM_FULL", "La stanza ha raggiunto il limite di 20 giocatori.")

        normalized_nickname = self._validate_nickname(nickname)
        nickname_key = normalized_nickname.casefold()
        if any(player.nickname.casefold() == nickname_key for player in room.players.values()):
            raise RoomError("NICKNAME_ALREADY_EXISTS", "Questo nickname e' gia utilizzato nella stanza.")

        player = Player(id=str(uuid4()), nickname=normalized_nickname, is_host=False, connected=True)
        room.players[player.id] = player
        token = self._register_player_token(room, player)
        return room, player, token

    def get_room(self, code: str) -> Room:
        normalized_code = self._normalize_code(code)
        room = self.rooms.get(normalized_code)
        if room is None:
            if normalized_code in self.closed_codes:
                raise RoomError("ROOM_CLOSED", "Questa stanza e' stata chiusa.")
            raise RoomError("ROOM_NOT_FOUND", "Stanza non trovata.")
        return room

    def get_room_for_player_token(self, token: str | None) -> tuple[Room, Player] | None:
        if not token:
            return None
        session = self.player_tokens.get(self._hash_token(token))
        if session is None:
            return None
        room_id, player_id = session
        room = next((item for item in self.rooms.values() if item.id == room_id), None)
        player = room.players.get(player_id) if room else None
        if room is None or player is None:
            return None
        return room, player

    def get_host_room(self, code: str, host_user_id: str) -> tuple[Room, Player]:
        room = self.get_room(code)
        if room.host_user_id != host_user_id:
            raise RoomError("HOST_PERMISSION_REQUIRED", "Solo l'host puo eseguire questa operazione.")
        return room, room.players[room.host_player_id]

    def connect_player(self, token: str | None, socket_id: str) -> tuple[Room, Player] | None:
        result = self.get_room_for_player_token(token)
        if result is None:
            return None
        room, player = result
        player.connected = True
        player.socket_id = socket_id
        return room, player

    def disconnect_socket(self, socket_id: str) -> tuple[Room, Player] | None:
        for room in self.rooms.values():
            for player in room.players.values():
                if player.socket_id == socket_id:
                    player.connected = False
                    player.socket_id = None
                    return room, player
        return None

    def leave_room(self, token: str | None) -> Room:
        result = self.get_room_for_player_token(token)
        if result is None:
            raise RoomError("PLAYER_SESSION_INVALID", "Sessione giocatore non valida.")
        room, player = result
        if player.is_host:
            raise RoomError("HOST_CANNOT_LEAVE", "L'host deve chiudere la stanza.")
        room.players.pop(player.id)
        self.player_tokens.pop(self._hash_token(token or ""), None)
        return room

    def close_room(self, host_user_id: str, code: str) -> Room:
        room, _ = self.get_host_room(code, host_user_id)
        room.status = RoomStatus.CLOSED
        self.rooms.pop(room.code, None)
        self.closed_codes.add(room.code)
        for player in room.players.values():
            self._remove_player_tokens(room.id, player.id)
        return room

    def _new_code(self) -> str:
        for _ in range(100):
            code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(4))
            if code not in self.rooms and code not in self.closed_codes:
                return code
        raise RoomError("ROOM_CODE_UNAVAILABLE", "Impossibile generare un codice stanza.")

    @staticmethod
    def _normalize_code(code: str) -> str:
        normalized = code.strip().upper()
        if len(normalized) != 4 or not normalized.isalpha():
            raise RoomError("INVALID_ROOM_CODE", "Il codice stanza deve contenere 4 lettere.")
        return normalized

    @staticmethod
    def _validate_nickname(nickname: str) -> str:
        normalized = " ".join(nickname.strip().split())
        if not NICKNAME_MIN_LENGTH <= len(normalized) <= NICKNAME_MAX_LENGTH:
            raise RoomError("INVALID_NICKNAME", "Il nickname deve contenere da 1 a 24 caratteri.")
        return normalized

    def _register_player_token(self, room: Room, player: Player) -> str:
        token = secrets.token_urlsafe(32)
        self.player_tokens[self._hash_token(token)] = (room.id, player.id)
        return token

    def _remove_player_tokens(self, room_id: str, player_id: str) -> None:
        for token_hash, session in list(self.player_tokens.items()):
            if session == (room_id, player_id):
                self.player_tokens.pop(token_hash, None)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


room_manager = RoomManager()
