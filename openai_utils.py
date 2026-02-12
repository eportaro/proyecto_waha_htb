# openai_utils.py - OPTIMIZADO (versión corregida para copiar/pegar)

import os
import time
import re
import json
from dotenv import load_dotenv

load_dotenv()

_client = None
_thread_cache = {}  # Cache de threads por sesión

# ===== Textos =====
HELPDESK_CONTACTO = (
    "Si necesitas contactar al Helpdesk de Hermes, utiliza:\n"
    "• Correo: ithelpdesk@hermes.com.pe\n"
    "• Teléfono: (01) 617 4000 anexo 5555"
)

_HELPDESK_Q = re.compile(
    r"(helpdesk|mesa\s+de\s+ayuda|soporte\s+ti|soporte\s+t[ée]cnico|it\s*helpdesk|contact(o|ar)|tel[eé]fono|n[uú]mero|correo)",
    re.IGNORECASE
)

MAX_CTX_MSGS = int(os.getenv("MAX_CTX_MSGS", "20"))


def is_pure_greeting(text: str) -> bool:
    """Saludo 'puro' corto."""
    if not text:
        return False
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 1:
        return False
    t = lines[0]
    if len(t) > 25 or "?" in t or ":" in t:
        return False
    t_norm = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ'\s]", "", t, flags=re.UNICODE).lower().strip()
    t_norm = re.sub(r"\s+", " ", t_norm)
    greetings = {
        "hola", "buenas", "buenas tardes", "buenas noches",
        "buen dia", "buen día", "que tal", "qué tal",
        "gracias", "ok", "hola buen dia", "hola buen día",
        "hola buenos dias", "hola buenos días"
    }
    return t_norm in greetings


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if v in {"1", "true", "t", "yes", "y"}:
        return True
    if v in {"0", "false", "f", "no", "n"}:
        return False
    return default


def _get_client():
    """Cliente OpenAI con tolerancia SSL corporativa."""
    global _client
    if _client is not None:
        return _client

    from openai import OpenAI
    import httpx

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta OPENAI_API_KEY en el entorno (.env).")

    # Timeouts configurables
    http_timeout = float(os.getenv("OPENAI_TIMEOUT_SECS", "60"))
    timeout = httpx.Timeout(http_timeout)

    # Verificación SSL configurable (útil en proxys corporativos)
    verify_ssl = _env_bool("HTTPX_VERIFY", False)

    http_client = httpx.Client(verify=verify_ssl, timeout=timeout, follow_redirects=True)
    _client = OpenAI(api_key=api_key, http_client=http_client)
    return _client


def _wait_run_ok(client, thread_id: str, run_id: str, timeout_s: int = None):
    """Espera con polling progresivo hasta que el run complete o falle."""
    if timeout_s is None:
        timeout_s = int(os.getenv("ASSISTANTS_RUN_TIMEOUT_SECS", "90"))

    t0 = time.time()
    intervals = [0.3, 0.5, 0.7, 1.0]  # Intervalos progresivos
    idx = 0

    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)

        if run.status == "completed":
            return

        if run.status in ("failed", "expired", "cancelled"):
            # Intentar obtener detalle de error si existe
            last_error = getattr(run, "last_error", None)
            raise RuntimeError(f"Assistant run {run.status}: {last_error or 'Sin detalles'}")

        if run.status == "requires_action":
            # Si no manejas tools, es mejor fallar explícitamente
            raise RuntimeError("Assistant run requires_action (no hay handler de tools implementado).")

        # Estados intermedios permitidos: queued, in_progress
        if time.time() - t0 > timeout_s:
            # Intentar cancelar el run antes de fallar
            try:
                client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
            except Exception:
                pass
            raise TimeoutError(f"Assistant tardó más de {timeout_s}s.")

        # Polling progresivo
        sleep_time = intervals[min(idx, len(intervals) - 1)]
        time.sleep(sleep_time)
        idx += 1


def _strip_fake_citations(text: str) -> str:
    """Limpia citas sintéticas."""
    if not text:
        return text
    t = re.sub(r"【[^【】]*】", "", text).strip()
    t = re.sub(r"\[\d+(?:-\d+)?\]", "", t).strip()
    return t


def _get_or_create_thread(session_id: str):
    """
    Reutiliza thread por sesión para evitar crear uno nuevo cada vez.
    CLAVE para velocidad: mantiene contexto en OpenAI.
    """
    global _thread_cache
    if session_id in _thread_cache:
        return _thread_cache[session_id]

    client = _get_client()
    thread = client.beta.threads.create()
    _thread_cache[session_id] = thread.id

    # Limpieza simple de cache viejo (no LRU real)
    if len(_thread_cache) > 100:
        # Eliminar los 20 más antiguos por orden de inserción
        items = list(_thread_cache.items())
        for k, _ in items[:20]:
            _thread_cache.pop(k, None)

    return thread.id


def ask_openai(question: str, history: list | None = None, allow_greeting: bool = True, session_id: str = None) -> str:
    """
    OPTIMIZADO: Reutiliza thread por sesión para respuestas más rápidas.
    Args:
        question: Pregunta del usuario
        history: Historial (no se usa para crear thread; contexto persistente vive en el thread)
        allow_greeting: Permite saludos
        session_id: ID de sesión para reutilizar thread
    """
    if allow_greeting and is_pure_greeting(question):
        return "¡Hola! 😊 Soy el asistente de soporte TI de Hermes. ¿En qué puedo ayudarte?"

    if _HELPDESK_Q.search(question):
        return HELPDESK_CONTACTO

    client = _get_client()
    assistant_id = os.getenv("ASSISTANT_ID", "").strip()
    if not assistant_id:
        raise RuntimeError("Falta ASSISTANT_ID en .env")

    # Reutilizar/crear thread
    if session_id:
        thread_id = _get_or_create_thread(session_id)
    else:
        thread = client.beta.threads.create()
        thread_id = thread.id

    # Agregar solo el mensaje nuevo (el historial ya está en el thread si lo has ido usando)
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=question
    )

    # Ejecutar assistant run
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    _wait_run_ok(client, thread_id, run.id, timeout_s=int(os.getenv("ASSISTANTS_RUN_TIMEOUT_SECS", "90")))

    # Obtener respuesta más reciente del asistente (no del usuario)
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=5)
    assistant_msg = next((m for m in messages.data if getattr(m, "role", "") == "assistant"), None)

    if not assistant_msg:
        return (
            "No pude generar una respuesta en este momento. "
            "¿Deseas que lo derive al Helpdesk o que cree un ticket en iTop?\n" + HELPDESK_CONTACTO
        )

    chunks = []
    for p in assistant_msg.content:
        if p.type == "text" and getattr(p, "text", None):
            chunks.append(p.text.value)

    answer = "\n".join(chunks).strip()
    answer = _strip_fake_citations(answer)

    if not answer or len(answer) < 5:
        return (
            "No pude generar una respuesta útil. "
            "¿Deseas que lo derive al Helpdesk o que cree un ticket en iTop?\n" + HELPDESK_CONTACTO
        )

    return answer


def clear_thread_cache(session_id: str = None):
    """Limpia el cache de threads (útil cuando se resetea sesión)."""
    global _thread_cache
    if session_id:
        _thread_cache.pop(session_id, None)
    else:
        _thread_cache.clear()


def generar_resumen_ticket(historial: list) -> tuple[str, str]:
    """Genera título y descripción para ticket (optimizado)."""
    client = _get_client()

    # Limitar historial para resumen
    hist = historial[-10:] if len(historial) > 10 else historial

    messages = [
        {
            "role": "system",
            "content": "Resume en 2 líneas:\n1) Título breve (max 100 chars)\n2) Descripción del problema"
        }
    ] + hist

    try:
        r = client.chat.completions.create(
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            messages=messages,
            temperature=0.3,
            max_tokens=200  # Limitar tokens
        )
        text = (r.choices[0].message.content or "").strip()
        if "\n" in text:
            lines = text.split("\n", 1)
            return lines[0].strip()[:100], lines[1].strip()
        return text[:100].strip(), text
    except Exception as e:
        return "Incidente reportado", f"Error generando resumen: {e}"


def extraer_incidentes(historial: list) -> list[dict]:
    """Detecta incidentes (optimizado)."""
    client = _get_client()

    # Limitar historial
    hist = historial[-15:] if len(historial) > 15 else historial
    prompt = (
        "Analiza y devuelve JSON con lista 'incidents'.\n"
        "Cada item: {title: string, description: string}\n"
        "Máximo 5 incidentes. Solo si ameritan ticket de soporte TI."
    )

    try:
        r = client.chat.completions.create(
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            messages=[{"role": "system", "content": prompt}] + hist,
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        content = (r.choices[0].message.content or "").strip()
        js = json.loads(content)
        incidents = js.get("incidents", [])

        # Validar y limpiar
        valid_incidents = []
        for inc in incidents[:5]:  # Max 5
            if isinstance(inc, dict) and inc.get("title"):
                valid_incidents.append({
                    "title": str(inc.get("title", ""))[:120],
                    "description": str(inc.get("description", ""))[:500]
                })

        if valid_incidents:
            return valid_incidents

        t, d = generar_resumen_ticket(hist)
        return [{"title": t, "description": d}]

    except Exception as e:
        print(f"[WARN] Error extrayendo incidentes: {e}")
        t, d = generar_resumen_ticket(hist)
        return [{"title": t, "description": d}]
