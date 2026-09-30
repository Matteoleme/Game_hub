import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { FormEvent, useEffect, useState } from "react";
import { io } from "socket.io-client";
import "./styles.css";

type User = { id: string; email: string; created_at: string };
type AuthResponse = { user: User };
type Player = { id: string; nickname: string; is_host: boolean; connected: boolean; score: number };
type Game = { id: string; room_id: string; mode: string; status: string; phase: string; started_at: string; finished_at: string | null; mode_state: Record<string, unknown> };
type Room = { id: string; code: string; status: string; host_player_id: string; created_at: string; players: Player[]; selected_mode: string | null; current_game: Game | null; cumulative_scores: Record<string, number>; completed_games: CompletedGame[] };
type CompletedGame = { id: string; room_id: string; mode: string; status: string; started_at: string; finished_at: string | null; points_by_player: Record<string, number> };
type GameMode = { id: string; name: string; available: boolean };
type RevealVote = { voterPlayerId: string; voterNickname: string; targetPlayerId: string; targetNickname: string; correct: boolean; pointsEarned: number };
type RevealStory = { id: string; text: string; authorPlayerId: string; authorNickname: string; votes: RevealVote[] };

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "";
const roomStorageKey = "game-hub-room-code";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  const body = (await response.json().catch(() => null)) as T & {
    detail?: { message?: string };
  } | null;
  if (!response.ok) {
    throw new Error(body?.detail?.message ?? "Operazione non riuscita.");
  }
  return body as T;
}

function App() {
  return (
    <AuthPage />
  );
}

function AuthPage() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [room, setRoom] = useState<Room | null>(null);

  useEffect(() => {
    async function restoreSession() {
      try {
        const { user: currentUser } = await request<AuthResponse>("/api/auth/me");
        setUser(currentUser);
      } catch {
        // Guests have no host session, but can still restore through player cookie.
      }
      const storedCode = window.localStorage.getItem(roomStorageKey);
      if (storedCode) {
        try {
          const restoredRoom = await request<Room>(`/api/rooms/${storedCode}`);
          setRoom(restoredRoom);
        } catch {
          window.localStorage.removeItem(roomStorageKey);
        }
      }
      setLoading(false);
    }

    void restoreSession();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const result = await request<AuthResponse>(path, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (mode === "login") setUser(result.user);
      else setMode("login");
      setPassword("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Operazione non riuscita.");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await request<void>("/api/auth/logout", { method: "POST" });
    setUser(null);
  }

  if (room) {
    return <RoomLobby room={room} isHost={Boolean(user)} onExit={() => { window.localStorage.removeItem(roomStorageKey); setRoom(null); }} />;
  }

  return (
    <main className="app-shell">
      <section className="welcome-panel" aria-labelledby="page-title">
        <p className="eyebrow">PARTY GAME HUB</p>
        <h1 id="page-title">La serata comincia qui.</h1>
        <p className="intro">
          Un unico spazio per riunire gli amici, scegliere una sfida e tenere il
          punteggio della serata.
        </p>
        {user ? (
          <div className="auth-panel">
            <p className="panel-label">HOST AUTENTICATO</p>
            <strong>{user.email}</strong>
            <RoomCreator onCreated={(createdRoom) => { window.localStorage.setItem(roomStorageKey, createdRoom.code); setRoom(createdRoom); }} />
            <button type="button" onClick={logout}>Esci</button>
          </div>
        ) : (
          <form className="auth-panel" onSubmit={submit}>
            <div className="mode-switch" role="tablist" aria-label="Accesso host">
              <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Accedi</button>
              <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Registrati</button>
            </div>
            <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="submit-button" type="submit" disabled={loading}>{loading ? "Attendi..." : mode === "login" ? "Accedi" : "Crea account"}</button>
          </form>
        )}
        {!user && <GuestJoin onJoined={(joinedRoom) => { window.localStorage.setItem(roomStorageKey, joinedRoom.code); setRoom(joinedRoom); }} />}
        <div className="status-row" role="status">
          <span className="status-dot" aria-hidden="true" />
          Foundation online
        </div>
      </section>
    </main>
  );
}

function RoomCreator({ onCreated }: { onCreated: (room: Room) => void }) {
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await request<Room>("/api/rooms", { method: "POST", body: JSON.stringify({ nickname }) });
      onCreated(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Impossibile creare la stanza.");
    }
  }

  return (
    <form className="room-create" onSubmit={create}>
      <p className="panel-label">NUOVA STANZA</p>
      <label>Il tuo nickname<input value={nickname} onChange={(event) => setNickname(event.target.value)} maxLength={24} required /></label>
      {error && <p className="form-error">{error}</p>}
      <button className="submit-button" type="submit">Crea stanza</button>
    </form>
  );
}

function GuestJoin({ onJoined }: { onJoined: (room: Room) => void }) {
  const [code, setCode] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");

  async function join(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await request<Room>(`/api/rooms/${code}/join`, { method: "POST", body: JSON.stringify({ nickname }) });
      onJoined(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Impossibile entrare nella stanza.");
    }
  }

  return (
    <form className="room-create guest-join" onSubmit={join}>
      <p className="panel-label">ENTRA COME GUEST</p>
      <label>Codice stanza<input value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} maxLength={4} required /></label>
      <label>Nickname<input value={nickname} onChange={(event) => setNickname(event.target.value)} maxLength={24} required /></label>
      {error && <p className="form-error">{error}</p>}
      <button className="submit-button" type="submit">Entra nella stanza</button>
    </form>
  );
}

function RoomLobby({ room: initialRoom, isHost, onExit }: { room: Room; isHost: boolean; onExit: () => void }) {
  const [room, setRoom] = useState(initialRoom);
  const [modes, setModes] = useState<GameMode[]>([]);
  const [error, setError] = useState("");
  const [storySubmitted, setStorySubmitted] = useState(false);
  const [votedStoryIds, setVotedStoryIds] = useState<string[]>([]);

  useEffect(() => {
    setStorySubmitted(false);
    setVotedStoryIds([]);
  }, [room.current_game?.id]);

  useEffect(() => {
    request<GameMode[]>("/api/game-modes").then(setModes).catch(() => setError("Impossibile caricare le modalita."));
  }, []);

  useEffect(() => {
    const socket = io(apiBaseUrl || window.location.origin, { withCredentials: true });
    socket.on("room:updated", (updatedRoom: Room) => setRoom(updatedRoom));
    socket.on("game:started", (updatedRoom: Room) => setRoom(updatedRoom));
    socket.on("game:finished", (updatedRoom: Room) => setRoom(updatedRoom));
    socket.on("room:closed", () => onExit());
    socket.on("error", (socketError: { message?: string }) => setError(socketError.message ?? "Errore di connessione."));
    return () => {
      socket.disconnect();
    };
  }, []);

  async function closeRoom() {
    await request(`/api/rooms/${room.code}/close`, { method: "POST" });
    onExit();
  }

  async function leaveRoom() {
    await request(`/api/rooms/${room.code}/leave`, { method: "POST" });
    onExit();
  }

  async function selectMode(modeId: string) {
    try {
      const updatedRoom = await request<Room>(`/api/rooms/${room.code}/mode`, { method: "POST", body: JSON.stringify({ mode_id: modeId }) });
      setRoom(updatedRoom);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Impossibile selezionare la modalita.");
    }
  }

  async function startGame() {
    try {
      const updatedRoom = await request<Room>(`/api/rooms/${room.code}/start`, { method: "POST" });
      setRoom(updatedRoom);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Impossibile iniziare la partita.");
    }
  }

  async function finishGame() {
    const updatedRoom = await request<Room>(`/api/rooms/${room.code}/finish`, { method: "POST" });
    setRoom(updatedRoom);
  }

  return (
    <main className="app-shell">
      <section className="welcome-panel lobby-panel" aria-labelledby="room-title">
        <p className="eyebrow">LOBBY</p>
        <h1 id="room-title" className="room-code">{room.code}</h1>
        <p className="intro">Condividi il codice con il tuo gruppo. La partita verra aggiunta nella prossima milestone.</p>
        <div className="player-list">
          <p className="panel-label">GIOCATORI {room.players.length} / 20</p>
          {room.players.map((player) => (
            <div className="player-row" key={player.id}><span className={player.connected ? "status-dot" : "status-dot offline"} />{player.nickname}{player.is_host && <small>HOST</small>}</div>
          ))}
        </div>
        {room.completed_games.length > 0 && <GameHistory games={room.completed_games} players={room.players} />}
        <div className="mode-selector">
          <p className="panel-label">MODALITA</p>
          {modes.map((mode) => (
            <button key={mode.id} type="button" disabled={!isHost || !mode.available || room.current_game !== null} className={room.selected_mode === mode.id ? "mode-option selected" : "mode-option"} onClick={() => selectMode(mode.id)}>
              <span>{mode.name}</span><small>{mode.available ? (room.selected_mode === mode.id ? "SELEZIONATA" : "DISPONIBILE") : "PRESTO"}</small>
            </button>
          ))}
        </div>
        {room.current_game ? (
          <div className="game-status">
            <p className="panel-label">PARTITA ATTIVA</p>
            <strong>{room.current_game.mode}</strong>
            <span>Fase: {room.current_game.phase}</span>
            {room.current_game.mode === "anecdotes" && room.current_game.phase === "WRITING" && (
              <AnecdoteWriting
                room={room}
                disabled={storySubmitted}
                onSubmitted={(updatedRoom) => {
                  setStorySubmitted(true);
                  setRoom(updatedRoom);
                }}
              />
            )}
            {room.current_game.mode === "anecdotes" && room.current_game.phase === "VOTING" && (
              <AnecdoteVoting
                room={room}
                votedStoryIds={votedStoryIds}
                onVoted={(updatedRoom, storyId) => {
                  setVotedStoryIds((current) => [...current, storyId]);
                  setRoom(updatedRoom);
                }}
                onError={setError}
              />
            )}
            {room.current_game.mode === "anecdotes" && room.current_game.phase === "REVEAL" && (
              <AnecdoteReveal room={room} />
            )}
            {room.current_game.phase === "REVEAL" && isHost && <button className="submit-button" type="button" onClick={finishGame}>Torna alla lobby</button>}
          </div>
        ) : isHost ? (
          <button className="submit-button" type="button" disabled={room.players.length < 3 || room.selected_mode === null} onClick={startGame}>Inizia partita</button>
        ) : (
          <p className="waiting-copy">Attendi che l'host scelga una modalita e inizi la partita.</p>
        )}
        {error && <p className="form-error">{error}</p>}
        {isHost ? <button className="submit-button" type="button" onClick={closeRoom}>Chiudi stanza</button> : <button className="submit-button" type="button" onClick={leaveRoom}>Esci dalla stanza</button>}
      </section>
    </main>
  );
}

function GameHistory({ games, players }: { games: CompletedGame[]; players: Player[] }) {
  return (
    <div className="history-panel">
      <p className="panel-label">PARTITE CONCLUSE</p>
      {games.map((game, index) => (
        <div className="history-row" key={game.id}>
          <span>#{index + 1} {game.mode}</span>
          <span>{Object.entries(game.points_by_player).map(([playerId, points]) => `${players.find((player) => player.id === playerId)?.nickname ?? "Player"} +${points}`).join(" · ")}</span>
        </div>
      ))}
    </div>
  );
}

function AnecdoteReveal({ room }: { room: Room }) {
  const state = room.current_game?.mode_state as { revealStories?: RevealStory[] };
  return (
    <div className="reveal-panel">
      <p className="panel-label">REVEAL</p>
      {state.revealStories?.map((story, index) => (
        <article className="reveal-story" key={story.id}>
          <p className="panel-label">ANEDDOTO {index + 1}</p>
          <p className="reveal-text">{story.text}</p>
          <strong>Autore: {story.authorNickname}</strong>
          <div className="reveal-votes">{story.votes.map((vote) => <div className={vote.correct ? "reveal-vote correct" : "reveal-vote"} key={vote.voterPlayerId}><span>{vote.voterNickname} → {vote.targetNickname}</span><small>{vote.pointsEarned > 0 ? `+${vote.pointsEarned}` : "0"}</small></div>)}</div>
        </article>
      ))}
      <div className="score-list"><p className="panel-label">PUNTEGGIO TOTALE</p>{room.players.map((player) => <div className="player-row" key={player.id}><span>{player.nickname}</span><strong>{player.score}</strong></div>)}</div>
    </div>
  );
}

function AnecdoteVoting({ room, votedStoryIds, onVoted, onError }: { room: Room; votedStoryIds: string[]; onVoted: (room: Room, storyId: string) => void; onError: (message: string) => void }) {
  const state = room.current_game?.mode_state as { currentStory?: { id: string; text: string }; currentStoryIndex?: number; totalStories?: number; votesReceived?: number; eligibleVotes?: number };
  const story = state.currentStory;
  if (!story) return null;
  const currentStory = story;
  const hasVoted = votedStoryIds.includes(story.id);

  async function vote(targetPlayerId: string) {
    onError("");
    try {
      const updatedRoom = await request<Room>(`/api/rooms/${room.code}/vote`, { method: "POST", body: JSON.stringify({ target_player_id: targetPlayerId }) });
      onVoted(updatedRoom, currentStory.id);
    } catch (requestError) {
      onError(requestError instanceof Error ? requestError.message : "Voto non valido.");
    }
  }

  return (
    <div className="voting-panel">
      <div className="story-card"><p className="panel-label">ANEDDOTO {(state.currentStoryIndex ?? 0) + 1} / {state.totalStories}</p><p>{currentStory.text}</p></div>
      <div className="writing-meta"><span>Voti ricevuti</span><span>{state.votesReceived ?? 0} / {state.eligibleVotes ?? 0}</span></div>
      {hasVoted ? <p className="waiting-copy">Voto inviato. Attendi gli altri giocatori.</p> : <div className="candidate-list">{room.players.map((player) => <button className="candidate-button" key={player.id} type="button" onClick={() => vote(player.id)}>{player.nickname}</button>)}</div>}
    </div>
  );
}

function AnecdoteWriting({ room, disabled, onSubmitted }: { room: Room; disabled: boolean; onSubmitted: (room: Room) => void }) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const progress = room.current_game?.mode_state as { submittedPlayerIds?: string[]; totalPlayers?: number } | undefined;
  const submittedCount = progress?.submittedPlayerIds?.length ?? 0;
  const totalPlayers = progress?.totalPlayers ?? room.players.length;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const updatedRoom = await request<Room>(`/api/rooms/${room.code}/story`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      onSubmitted(updatedRoom);
      setText("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Impossibile inviare l'aneddoto.");
    }
  }

  return (
    <form className="writing-panel" onSubmit={submit}>
      <label>Qual e una cosa assurda che ti e successa?
        <textarea value={text} onChange={(event) => setText(event.target.value)} maxLength={500} minLength={1} disabled={disabled} required />
      </label>
      <div className="writing-meta"><span>{text.length} / 500</span><span>{submittedCount} / {totalPlayers} inviati</span></div>
      {disabled && <p className="waiting-copy">Aneddoto inviato. Attendi gli altri giocatori.</p>}
      {error && <p className="form-error">{error}</p>}
      {!disabled && <button className="submit-button" type="submit">Invia aneddoto</button>}
    </form>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
