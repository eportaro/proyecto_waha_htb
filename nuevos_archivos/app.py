from flask import Flask, request, jsonify
from bot.ai_bot import AIBot
from services.waha import Waha
import traceback

app = Flask(__name__)

# Instancias únicas
print("🚀 Inicializando servicios...", flush=True)
WAHA = Waha()
BOT = AIBot()
print("✅ Servicios iniciados correctamente", flush=True)

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check"""
    return jsonify({
        "status": "ok",
        "service": "WhatsApp Bot API",
        "sessions_active": len(BOT.sessions)
    }), 200

@app.route('/chatbot/webhook', methods=['POST'])
@app.route('/chatbot/webhook/', methods=['POST'])
def webhook():
    """
    Webhook principal para recibir mensajes de WAHA.
    """
    data = request.json or {}
    chat_id = None

    try:
        # Extraer datos del webhook
        event = data.get("event")
        payload = data.get("payload", {})
        
        # Obtener chat_id y mensaje
        chat_id = payload.get("from") or payload.get("chatId") or ""
        received_message = payload.get("body") or payload.get("text") or ""
        
        if not chat_id:
            print("⚠️ Webhook recibido sin chat_id", flush=True)
            return jsonify({"status": "ignored", "reason": "no chat_id"}), 200

        # Ignorar grupos y estados
        if "@g.us" in chat_id or "@broadcast" in chat_id:
            return jsonify({'status': 'ignored', 'reason': 'group or broadcast'}), 200

        # Ignorar mensajes del bot mismo
        if payload.get("fromMe", False):
            return jsonify({'status': 'ignored', 'reason': 'message from bot'}), 200

        print(f"\n{'='*60}", flush=True)
        print(f"📨 MENSAJE RECIBIDO", flush=True)
        print(f"Chat ID: {chat_id}", flush=True)
        print(f"Mensaje: {received_message}", flush=True)
        print(f"{'='*60}\n", flush=True)

        # Marcar como visto
        WAHA.send_seen(chat_id=chat_id)
        
        # Indicador de escritura
        WAHA.start_typing(chat_id=chat_id)

        # Procesar con el bot
        try:
            response_message = BOT.process(chat_id, received_message)
        except Exception as bot_error:
            print(f"❌ Error en BOT.process: {bot_error}", flush=True)
            print(traceback.format_exc(), flush=True)
            response_message = (
                "⚠️ Disculpa, tuve un problema procesando tu mensaje.\n\n"
                "Por favor intenta nuevamente o escribe *ayuda* para ver las opciones disponibles."
            )

        if not response_message:
            response_message = (
                "⚠️ No pude procesar tu mensaje.\n\n"
                "Escribe *ayuda* para ver las opciones o *empezar* para iniciar tu postulación."
            )

        print(f"🤖 RESPUESTA BOT: {response_message[:100]}...", flush=True)

        # Enviar respuesta
        try:
            WAHA.send_message(chat_id=chat_id, message=response_message)
            print("✅ Respuesta enviada exitosamente", flush=True)
        except Exception as send_error:
            print(f"❌ Error al enviar mensaje: {send_error}", flush=True)
            print(traceback.format_exc(), flush=True)
            # Intentar enviar un mensaje de error simplificado
            try:
                WAHA.send_message(
                    chat_id=chat_id, 
                    message="⚠️ Hubo un problema al enviar la respuesta. Por favor intenta nuevamente."
                )
            except:
                pass

        return jsonify({'status': 'ok', 'processed': True}), 200

    except Exception as e:
        error_msg = f"Error general en webhook: {e}"
        print(f"❌ {error_msg}", flush=True)
        print(traceback.format_exc(), flush=True)
        
        # Intentar notificar al usuario del error
        if chat_id:
            try:
                WAHA.send_message(
                    chat_id=chat_id,
                    message="⚠️ Ocurrió un error inesperado. Por favor intenta más tarde o contacta con soporte."
                )
            except:
                pass
        
        return jsonify({'status': 'error', 'detail': str(e)}), 500

    finally:
        # Detener indicador de escritura
        if chat_id:
            try:
                WAHA.stop_typing(chat_id=chat_id)
            except:
                pass

@app.route('/sessions', methods=['GET'])
def get_sessions():
    """Endpoint para ver sesiones activas (debug)"""
    try:
        sessions_info = {}
        for chat_id, session in BOT.sessions.items():
            sessions_info[chat_id] = {
                "step": session["current_step"],
                "completed": session["completed"],
                "last_activity": session["last_activity"].isoformat(),
                "answers_count": len(session["answers"])
            }
        return jsonify({
            "total_sessions": len(sessions_info),
            "sessions": sessions_info
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear_session/<chat_id>', methods=['POST'])
def clear_session(chat_id):
    """Endpoint para limpiar una sesión específica (admin)"""
    try:
        if chat_id in BOT.sessions:
            del BOT.sessions[chat_id]
            return jsonify({"status": "ok", "message": f"Sesión {chat_id} eliminada"}), 200
        else:
            return jsonify({"status": "not_found", "message": "Sesión no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🤖 WhatsApp Bot API - Hermes Transportes Blindados")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5006, debug=True)