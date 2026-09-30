import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { FormEvent, useEffect, useState } from "react";
import "./styles.css";

type User = { id: string; email: string; created_at: string };
type AuthResponse = { user: User };

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "";

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

  useEffect(() => {
    request<AuthResponse>("/api/auth/me")
      .then(({ user: currentUser }) => setUser(currentUser))
      .catch(() => undefined)
      .finally(() => setLoading(false));
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
        <div className="status-row" role="status">
          <span className="status-dot" aria-hidden="true" />
          Foundation online
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
