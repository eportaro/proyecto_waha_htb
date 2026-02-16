# app.py
from __future__ import annotations

import os
import traceback
import time
from flask import Flask, request, jsonify

# ────────────────────────────────────────────────────────────────
# IMPORTS FLEXIBLES (funciona con o sin carpetas "services"/"bot")
# ────────────────────────────────────────────────────────────────
try:
    from services.waha import Waha
except ImportError:
    from waha import Waha

try:
    from bot.ai_bot import AIBot
except ImportError:
    from ai_bot import AIBot

try:
    from services.database import Database
except ImportError:
    from database import Database


# ────────────────────────────────────────────────────────────────
# INICIALIZACIÓN DE SERVICIOS
# ────────────────────────────────────────────────────────────────
app = Flask(__name__)

print("🚀 Inicializando servicios...", flush=True)
DB = Database()            # 1) Base de datos (Supabase o JSON local)
BOT = AIBot(db=DB)         # 2) Bot con IA (Gemini opcional) + DB inyectada
WAHA = Waha()              # 3) Cliente WAHA
print("✅ Servicios iniciados correctamente", flush=True)


# ────────────────────────────────────────────────────────────────
# RUTAS BÁSICAS / SALUD
# ────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "WhatsApp Bot API (RRHH)",
        "health": "ok",
        "sessions_active": len(BOT.sessions)
    }), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "WhatsApp Bot API",
        "sessions_active": len(BOT.sessions)
    }), 200


# ────────────────────────────────────────────────────────────────
# UTIL: EXTRACCIÓN ROBUSTA DE TEXTO Y CHAT_ID DESDE WAHA
# ────────────────────────────────────────────────────────────────
def _extract_chat_and_text(payload: dict) -> tuple[str | None, str]:
    # 1. Intentar obtener el ID real del usuario desde la metadata interna de Waha (_data)
    # Esto es critico porque 'from' puede ser un LID o ID de grupo
    chat_id = None

    # Prioridad 1: _data.id.user (Suele ser el numero limpio: 51999999999)
    try:
        user_part = payload.get("_data", {}).get("id", {}).get("user")
        if user_part and user_part.isdigit():
            # Reconstruir formato standard @c.us si es necesario,
            # pero mejor usemos lo que el bot espera
            chat_id = f"{user_part}@c.us"
    except: pass

    # Prioridad 2: _data.id.remote (Suele ser el JID completo: 51999999999@c.us)
    if not chat_id:
        try:
              remote = payload.get("_data", {}).get("id", {}).get("remote")
              if remote and "@" in remote and "g.us" not in remote:
                   chat_id = remote
        except: pass

    # Prioridad 3: Fallback a los campos de nivel superior
    if not chat_id:
        chat_id = (
            payload.get("from")
            or payload.get("chatId")
            or payload.get("sender")
            or payload.get("author")
            or ""
        )

    text = (
        payload.get("body")
        or payload.get("text")
        or payload.get("message")
        or payload.get("caption")
        or ""
    )

    if not text and isinstance(payload.get("message"), dict):
        text = payload["message"].get("body") or payload["message"].get("text") or ""

    return chat_id, (text or "")


# ────────────────────────────────────────────────────────────────
# WEBHOOK PRINCIPAL (desde WAHA)
# ────────────────────────────────────────────────────────────────
@app.route("/chatbot/webhook", methods=["POST"])
@app.route("/chatbot/webhook/", methods=["POST"])
def webhook():
    data = request.json or {}
    chat_id = None

    try:
        event = (data.get("event") or "").lower()
        payload = data.get("payload", {}) or {}

        chat_id, received_message = _extract_chat_and_text(payload)

        if not chat_id:
            print("⚠️ Webhook sin chat_id. Payload=", payload, flush=True)
            return jsonify({"status": "ignored", "reason": "no chat_id"}), 200

        if "@g.us" in chat_id or "@broadcast" in chat_id:
            return jsonify({'status': 'ignored', 'reason': 'group/broadcast'}), 200

        if payload.get("fromMe", False):
            return jsonify({'status': 'ignored', 'reason': 'message from bot'}), 200

        allowed_prefixes = ("message", "text")
        if event and not any(event.startswith(p) for p in allowed_prefixes):
            return jsonify({'status': 'ignored', 'reason': f'event {event} not handled'}), 200

        print("\n" + "=" * 60, flush=True)
        print("📨 MENSAJE RECIBIDO", flush=True)
        print(f"Event: {event or '(no-event)'}", flush=True)
        print(f"Chat ID: {chat_id}", flush=True)
        print(f"Mensaje: {received_message}", flush=True)
        print("=" * 60 + "\n", flush=True)

        # ─────── CAMBIO #1: QUITAMOS sendSeen ───────
        try:
            WAHA.start_typing(chat_id=chat_id)
            time.sleep(2)   # <-- CAMBIO #2: delay para estabilidad
        except Exception:
            pass

        try:
            response_message = BOT.process(chat_id, received_message)
        except Exception as bot_error:
            print(f"❌ Error en BOT.process: {bot_error}", flush=True)
            print(traceback.format_exc(), flush=True)
            response_message = (
                "⚠️ Disculpa, tuve un problema procesando tu mensaje.\n"
                "Por favor intenta nuevamente o escribe *ayuda*."
            )

        if not response_message or not response_message.strip():
            response_message = (
                "⚠️ No pude procesar tu mensaje.\n"
                "Escribe *ayuda* o *empezar* para iniciar tu postulación."
            )

        print(f"🤖 RESPUESTA BOT: {response_message[:200]}...", flush=True)

        try:
            WAHA.send_message(chat_id=chat_id, message=response_message)
            print("✅ Respuesta enviada exitosamente", flush=True)
        except Exception as send_error:
            print(f"❌ Error al enviar mensaje: {send_error}", flush=True)
            print(traceback.format_exc(), flush=True)

            try:
                WAHA.send_message(
                    chat_id=chat_id,
                    message="⚠️ Ocurrió un error al enviar el mensaje. Intenta nuevamente."
                )
            except Exception:
                pass

        return jsonify({'status': 'ok', 'processed': True}), 200

    except Exception as e:
        print(f"❌ Error general en webhook: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        if chat_id:
            try:
                WAHA.send_message(
                    chat_id=chat_id,
                    message="⚠️ Ocurrió un error inesperado. Intenta más tarde."
                )
            except Exception:
                pass
        return jsonify({'status': 'error', 'detail': str(e)}), 500

    finally:
        if chat_id:
            try:
                WAHA.stop_typing(chat_id=chat_id)
            except Exception:
                pass


# ────────────────────────────────────────────────────────────────
# ENDPOINTS DE CONSULTA DE POSTULANTES
# ────────────────────────────────────────────────────────────────
@app.route("/postulantes", methods=["GET"])
def get_postulantes():
    try:
        limit = request.args.get("limit", 100, type=int)
        es_apto = request.args.get("es_apto")
        if es_apto is not None:
            es_apto = es_apto.lower() == "true"

        postulantes = DB.get_all_postulantes(limit=limit, es_apto=es_apto)
        return jsonify({"total": len(postulantes), "postulantes": postulantes}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/postulantes/<phone>", methods=["GET"])
def get_postulante(phone: str):
    try:
        postulante = DB.get_postulante(phone)
        if postulante:
            return jsonify(postulante), 200
        return jsonify({"error": "Postulante no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/postulantes/stats", methods=["GET"])
def get_stats():
    try:
        stats = DB.get_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/sessions", methods=["GET"])
def get_sessions():
    try:
        sessions_info = {}
        for chat_id, s in BOT.sessions.items():
            sessions_info[chat_id] = {
                "step": s.get("step"),
                "data": s.get("data"),
                "completed": s.get("completed"),
                "last_activity": (
                    s.get("last_activity").isoformat()
                    if s.get("last_activity") else None
                ),
            }
        return jsonify(sessions_info), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5006))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
