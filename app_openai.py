# app_openai.py — versión con puerto auto-libre + errores JSON (copiar/pegar)

import os
import html
import socket
import time
import uuid
import traceback
import sqlite3
import threading
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from itop_client import create_ticket, get_userrequest_by_ref
from email_utils import enviar_correo
from openai_utils import ask_openai, extraer_incidentes, is_pure_greeting, clear_thread_cache

# =========================
#        FastAPI
# =========================
app = FastAPI(title="Chatbot TI – Hermes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================
#  Errores JSON
# ================
@app.exception_handler(Exception)
async def _json_exception_handler(request: Request, exc: Exception):
    # Garantiza JSON ante cualquier error (evita HTML "Internal Server Error")
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": type(exc).__name__, "message": str(exc)[:300]},
    )

# =========================
#   Persistencia SQLite
# =========================
DB_PATH = os.getenv("SQLITE_PATH", "data/chatbot.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

_db_lock = threading.Lock()

def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def _db_init():
    with _get_conn() as cx:
        cx.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_ts  INTEGER NOT NULL,
            updated_ts  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            ts INTEGER NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_sid_ts ON messages(session_id, ts);
        """)
_db_init()

def _now() -> int:
    return int(time.time())

def _db_touch_session(session_id: str):
    t = _now()
    with _db_lock, _get_conn() as cx:
        cx.execute("""
        INSERT INTO sessions(session_id, created_ts, updated_ts)
        VALUES(?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET updated_ts=excluded.updated_ts
        """, (session_id, t, t))

def _db_append_message(session_id: str, role: str, content: str, ts: int | None = None):
    t = ts or _now()
    with _db_lock, _get_conn() as cx:
        cx.execute("""
            INSERT INTO messages(session_id, role, content, ts)
            VALUES (?, ?, ?, ?)
        """, (session_id, role, content, t))
        cx.execute("UPDATE sessions SET updated_ts=? WHERE session_id=?", (t, session_id))

def _db_get_history(session_id: str, limit: int | None = None):
    sql = "SELECT role, content, ts FROM messages WHERE session_id=? ORDER BY ts ASC"
    params = (session_id,)
    if limit and isinstance(limit, int) and limit > 0:
        sql += " LIMIT ?"
        params = (session_id, limit)
    with _db_lock, _get_conn() as cx:
        rows = cx.execute(sql, params).fetchall()
    return [{"role": r, "content": c, "ts": t} for (r, c, t) in rows]

def _db_gc_stale_sessions(days: int):
    cutoff = _now() - days*24*3600
    with _db_lock, _get_conn() as cx:
        old_sessions = [r[0] for r in cx.execute("SELECT session_id FROM sessions WHERE updated_ts < ?", (cutoff,))]
        if old_sessions:
            cx.executemany("DELETE FROM messages WHERE session_id=?", [(s,) for s in old_sessions])
            cx.executemany("DELETE FROM sessions WHERE session_id=?", [(s,) for s in old_sessions])

# =========================
#   Sesiones (RAM + lotes)
# =========================
TTL_SECONDS = 2 * 60 * 60
COALESCE_SEC = float(os.getenv("COALESCE_SEC", "2.0"))  # Ventana para agrupar mensajes
PURGE_DAYS = int(os.getenv("PURGE_DAYS", "2"))
INACTIVITY_RESET_MIN = int(os.getenv("INACTIVITY_RESET_MIN", "45"))
INACTIVITY_RESET_SEC = INACTIVITY_RESET_MIN * 60

SESSIONS: dict[str, dict] = {}

def _gc_sessions():
    t = _now()
    stale = [sid for sid, v in SESSIONS.items() if t - v.get("ts", 0) > TTL_SECONDS]
    for sid in stale:
        SESSIONS.pop(sid, None)
        clear_thread_cache(sid)  # limpia thread cache también
    
    # GC en BD cada ~minuto
    if t % 60 == 0:
        _db_gc_stale_sessions(days=PURGE_DAYS)

def _get_or_load_session(sid: str):
    cur = SESSIONS.get(sid)
    if not cur:
        msgs = _db_get_history(sid)
        cur = {
            "messages": msgs,
            "ts": _now(),
            "event": None,
            "batch_start": 0,
            "batch_answer": None,
            "coalesce_until": 0.0,
        }
        SESSIONS[sid] = cur
        _db_touch_session(sid)
    else:
        cur["ts"] = _now()
    return cur

def _history_for_model(messages: list[dict]):
    return [{"role": m["role"], "content": m["content"]} for m in messages]

# =========================
#          Rutas
# =========================
@app.get("/")
def home():
    return FileResponse("static/index.html")

@app.get("/static/{path:path}")
def static_files(path: str):
    full = os.path.join("static", path)
    if os.path.exists(full):
        return FileResponse(full)
    return JSONResponse({"error": "no encontrado"}, status_code=404)

@app.post("/api/ask")
async def api_ask(req: Request):
    # Siempre responder JSON (evitar 204 vacíos)
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)

    sid = body.get("session_id") or str(uuid.uuid4())
    q = (body.get("question") or "").strip()
    if not q:
        return JSONResponse({"error": "Pregunta vacía"}, status_code=400)

    _gc_sessions()
    state = _get_or_load_session(sid)

    # Auto-reset por inactividad
    now_i = _now()
    last_ts = state["messages"][-1]["ts"] if state["messages"] else 0
    if last_ts and (now_i - last_ts) > INACTIVITY_RESET_SEC:
        new_sid = str(uuid.uuid4())
        state = {
            "messages": [],
            "ts": _now(),
            "event": None,
            "batch_start": 0,
            "batch_answer": None,
            "coalesce_until": 0.0,
        }
        SESSIONS[new_sid] = state
        _db_touch_session(new_sid)
        clear_thread_cache(sid)
        sid = new_sid

    # Persistir mensaje de usuario
    ts = _now()
    user_msg = {"role": "user", "content": q, "ts": ts}
    state["messages"].append(user_msg)
    _db_touch_session(sid)
    _db_append_message(sid, "user", q, ts=ts)

    # Coalescer lote (agrupa ráfagas)
    is_leader = False
    ev = state.get("event")
    now = time.time()

    if ev is None or ev.is_set():
        ev = threading.Event()
        state["event"] = ev
        state["batch_start"] = ts
        state["batch_answer"] = None
        is_leader = True

    state["coalesce_until"] = max(state.get("coalesce_until", 0.0), now + COALESCE_SEC)

    # Esperar cierre de ventana
    while time.time() < state["coalesce_until"]:
        await asyncio.sleep(0.05)

    if is_leader:
        try:
            bstart = state["batch_start"]
            chunk_texts = [m["content"] for m in state["messages"] if m["role"] == "user" and m["ts"] >= bstart]
            combined = "\n".join(chunk_texts).strip()

            hist_for_model = _history_for_model(state["messages"])
            allow_greeting = (len(state["messages"]) <= 2) or is_pure_greeting(combined)

            # Reutiliza thread del Assistants API con session_id
            answer = ask_openai(
                combined, 
                hist_for_model, 
                allow_greeting=allow_greeting,
                session_id=sid
            )

            ats = _now()
            state["messages"].append({"role": "assistant", "content": answer, "ts": ats})
            _db_append_message(sid, "assistant", answer, ts=ats)

            state["batch_answer"] = answer
            ev.set()
            return {"answer": answer, "session_id": sid}

        except Exception as e:
            traceback.print_exc()
            error_msg = f"[Error] {type(e).__name__}: {str(e)[:100]}"
            state["batch_answer"] = error_msg
            ev.set()
            return {"answer": error_msg, "session_id": sid}

    # Seguidores: espera al líder y responde JSON siempre
    await asyncio.to_thread(ev.wait, 20)
    ans = state.get("batch_answer")
    if ans:
        # Ya respondió el líder → devolvemos 204 para que el front no pinte nada
        return JSONResponse(
            {"answer": None, "session_id": sid, "status": "coalesced_follower"},
            status_code=204,
        )

    # Si el líder aún no responde (caso raro), informa "processing"
    return JSONResponse(
        {"answer": None, "session_id": sid, "status": "processing"},
        status_code=202,
    )

@app.post("/api/incidents")
async def api_incidents(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)

    sid = body.get("session_id")
    if not sid:
        return JSONResponse({"error": "Falta session_id"}, status_code=400)

    _gc_sessions()
    state = _get_or_load_session(sid)
    
    # Ejecutar en thread para no bloquear
    incs = await asyncio.to_thread(
        extraer_incidentes, 
        _history_for_model(state["messages"])
    )
    
    return {"incidents": incs}

@app.post("/api/create_ticket")
async def api_create_ticket(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)

    sid   = body.get("session_id")
    email = (body.get("email") or "").strip()
    idxs  = body.get("indexes") or [0]

    if not sid:
        return JSONResponse({"ok": False, "error": "Falta session_id"}, status_code=400)

    _gc_sessions()
    state = _get_or_load_session(sid)

    incs = await asyncio.to_thread(
        extraer_incidentes,
        _history_for_model(state["messages"])
    )
    
    if not incs:
        return JSONResponse({"ok": False, "error": "No se detectaron incidentes."}, status_code=400)

    helpdesk_to = os.getenv("SMTP_HELPDESK_TO", "").strip()
    results = []

    for i in idxs:
        if not isinstance(i, int) or i < 0 or i >= len(incs):
            continue
        title = (incs[i].get("title") or "").strip()[:120] or "Incidente"
        desc  = (incs[i].get("description") or "").strip() or "Descripción no disponible."
        safe_desc = html.escape(desc).replace("\n", "<br>")

        # Crear ticket (thread separado)
        r = await asyncio.to_thread(create_ticket, title, safe_desc)
        ok  = bool(r.get("ok"))
        ref = r.get("ref") or "(sin ref)"

        # Enviar correos (si corresponde)
        destinatario_usuario = email or os.getenv("SMTP_TO", "")
        if destinatario_usuario:
            await asyncio.to_thread(
                enviar_correo,
                asunto=f"[Chatbot TI] Ticket {ref} - {title}",
                cuerpo=f"Se creó un ticket.\n\nAsunto: {title}\nReferencia: {ref}\n\nDescripción:\n{desc}",
                destinatario=destinatario_usuario
            )
        if helpdesk_to:
            await asyncio.to_thread(
                enviar_correo,
                asunto=f"[Chatbot TI] Nuevo Ticket {ref} - {title}",
                cuerpo=f"Origen: Chatbot TI\nRef: {ref}\nAsunto: {title}\n\nDescripción:\n{desc}",
                destinatario=helpdesk_to
            )

        results.append({"ok": ok, "ref": ref, "title": title})

    return {"ok": True, "results": results}

@app.post("/api/ticket_status")
async def api_ticket_status(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)

    ref = (body.get("ref") or "").strip()
    if not ref:
        return JSONResponse({"ok": False, "error": "Falta 'ref' de ticket"}, status_code=400)
    
    # Ejecutar en thread para no bloquear
    r = await asyncio.to_thread(get_userrequest_by_ref, ref)
    
    if not r.get("ok"):
        return JSONResponse({"ok": False, "error": r.get("error", "No encontrado")}, status_code=404)
    return {"ok": True, "fields": r["fields"]}

# =========================
#         Main
# =========================
def _get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
        return True

def _find_free_port(start_port: int = 8000, max_tries: int = 20) -> int:
    p = start_port
    for _ in range(max_tries):
        if _is_port_free(p):
            return p
        p += 1
    raise RuntimeError(f"No se encontró puerto libre desde {start_port}")

if __name__ == "__main__":
    desired = int(os.getenv("PORT", "8000"))
    port = _find_free_port(desired)

    lan_ip = _get_lan_ip()
    print(f"\n✅ Servidor activo en:\n→ Local: http://127.0.0.1:{port}\n→ LAN:   http://{lan_ip}:{port}\n")

    # Ejecuta SOLO así o SOLO con uvicorn por CLI (no ambos)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
