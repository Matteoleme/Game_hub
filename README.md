# Game Hub

Foundation di un hub per party game multiplayer, costruito per crescere per
milestone. La prima modalita prevista e Aneddoti; il gameplay verra aggiunto
nelle milestone successive.

## Milestone 1

Questa milestone include:

- backend FastAPI asincrono con `python-socketio` montato come ASGI;
- SQLAlchemy async su SQLite con WAL inizializzato all'avvio;
- endpoint `GET /api/health`;
- shell frontend React + TypeScript + Vite mobile-first;
- contratto protocollo iniziale in `shared/protocol/events.json`;
- Docker Compose con volume persistente per SQLite.

Non include ancora autenticazione, stanze, giocatori o gameplay.

## Milestone 2

La milestone di autenticazione host include:

- registrazione con email normalizzata e password validata;
- password memorizzate con hashing `scrypt`, mai in chiaro;
- login con sessione persistente in SQLite e cookie `HttpOnly`;
- logout e verifica della sessione tramite `GET /api/auth/me`;
- UI frontend per registrazione, accesso, ripristino sessione e logout;
- test backend per flusso completo, email duplicate e password non valide.

Le sessioni usano token casuali opachi: il cookie non contiene dati utente e nel
database viene memorizzato soltanto l'hash del token.

## Milestone 3

La milestone room include:

- creazione room da parte di un host autenticato;
- codice stanza casuale di 4 lettere maiuscole;
- ingresso guest con nickname e player token `HttpOnly`;
- nickname unici case-insensitive e limite massimo di 20 giocatori;
- stato live delle room mantenuto in RAM;
- lobby sincronizzata via Socket.IO;
- disconnessione temporanea senza rimozione del player;
- uscita guest e chiusura esplicita riservata all'host;
- frontend per creare, entrare e visualizzare la lobby.

Le room non vengono ancora persistite in SQLite e non esiste ancora il game
lifecycle: selezione modalità, avvio partita e punteggi appartengono alle
milestone successive.

## Milestone 4

La milestone game hub aggiunge:

- distinzione live tra `Room` persistente e `Game` singolo;
- registrazione SQLite di room e game conclusi;
- registro modalità con Aneddoti disponibile e modalità future disabilitate;
- selezione modalità riservata all'host;
- avvio game con almeno 3 player;
- stato generico `ACTIVE` / `FINISHED` del game;
- ritorno della room alla lobby senza rimuovere player o azzerare punteggi;
- punteggio cumulativo della room pronto per i delta delle modalità.

Il game Aneddoti non contiene ancora scrittura, voto o reveal: queste regole
arrivano nelle milestone 5, 6 e 7.

## Avvio locale

Prerequisiti: Python 3.12+ e Node.js 22+.

```powershell
Copy-Item .env.example .env
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
```

In un secondo terminale:

```powershell
cd frontend
npm install
npm run dev
```

Backend: `http://localhost:8000/api/health`  
Frontend: `http://localhost:5173`

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

L'applicazione sara disponibile su `http://localhost:8000`.

## Test backend

```powershell
backend/.venv/Scripts/Activate.ps1
pytest backend/tests
```

## Scelte architetturali iniziali

Il database viene preparato all'avvio ma non contiene ancora modelli di dominio:
lo stato live delle future room e game restera in RAM, mentre SQLite verra usato
per la persistenza necessaria alle milestone successive. Socket.IO e' gia
integrato al confine ASGI, ma gli eventi di dominio non sono ancora definiti.

Il contratto condiviso parte da JSON Schema per evitare una cartella TypeScript
falsamente condivisa. Potra essere esteso o affiancato da OpenAPI quando saranno
disponibili le API reali.