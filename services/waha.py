import os
import time
import requests
from typing import Optional, Dict, Any

class Waha:
    """
    Cliente robusto para WAHA (versión corregida y estable).
    """

    def __init__(self):
        self.base_url = os.getenv("WAHA_URL", "http://waha:3000").rstrip("/")
        self.api_key = os.getenv("WAHA_API_KEY", "")
        self.session = os.getenv("WAHA_SESSION", "default")

        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

        self._test_connection()

    def _test_connection(self):
        """Verifica la conexión con WAHA al inicializar"""
        try:
            url = f"{self.base_url}/api/server/status"
            r = requests.get(url, headers=self.headers, timeout=5)
            print(f"✅ WAHA conectado correctamente: {r.status_code}", flush=True)
        except Exception as e:
            print(
                f"⚠️ Advertencia: No se pudo verificar conexión con WAHA: {e}",
                flush=True,
            )

    def _post(self, path: str, payload: dict, timeout: int = 20) -> requests.Response:
        """Método base para hacer POST requests con mejores logs"""
        url = f"{self.base_url}{path}"
        try:
            r = requests.post(
                url, json=payload, headers=self.headers, timeout=timeout
            )
            print(f"📤 WAHA POST {path} -> Status: {r.status_code}", flush=True)

            if r.status_code >= 400:
                print(f"❌ WAHA ERROR BODY: {r.text}", flush=True)

            r.raise_for_status()
            return r

        except requests.exceptions.RequestException as e:
            print(f"❌ Error en WAHA POST {path}: {e}", flush=True)
            raise

    def send_message(self, chat_id: str, message: str) -> Optional[Dict[Any, Any]]:
        """
        Envía mensaje con el formato correcto y SIN rutas inexistentes.
        """

        if not message or not message.strip():
            print("⚠️ Intento de enviar mensaje vacío", flush=True)
            return None

        payload = {
            "chatId": chat_id,
            "text": message,
            "session": self.session,
        }

        try:
            r = self._post("/api/sendText", payload)
            print("✅ Mensaje enviado correctamente", flush=True)
            return r.json() if r.text else {}
        except Exception as e:
            print("❌ Falló sendText", flush=True)
            raise

    def start_typing(self, chat_id: str) -> bool:
        """Inicia el indicador de 'escribiendo...'"""
        payload = {"chatId": chat_id, "session": self.session}
        try:
            self._post("/api/startTyping", payload, timeout=10)
            return True
        except Exception as e:
            print(f"⚠️ Warning startTyping: {e}", flush=True)
            return False

    def stop_typing(self, chat_id: str) -> bool:
        """Detiene el indicador de 'escribiendo...'"""
        payload = {"chatId": chat_id, "session": self.session}
        try:
            self._post("/api/stopTyping", payload, timeout=10)
            return True
        except Exception as e:
            print(f"⚠️ Warning stopTyping: {e}", flush=True)
            return False

    def send_seen(self, chat_id: str) -> bool:
        """
        Marca como visto — LLAMAR SOLO DESPUÉS DE UN DELAY.
        """
        payload = {"chatId": chat_id, "session": self.session}
        try:
            time.sleep(3)  # <-- CLAVE para tu error actual
            self._post("/api/sendSeen", payload, timeout=10)
            return True
        except Exception as e:
            print(f"⚠️ Warning sendSeen: {e}", flush=True)
            return False

    def get_history_messages(self, chat_id: str, limit: int = 10) -> Optional[list]:
        """Obtiene historial de mensajes"""
        try:
            url = (
                f"{self.base_url}/api/{self.session}"
                f"/chats/{chat_id}/messages"
                f"?limit={limit}&downloadMedia=false"
            )
            r = requests.get(url, headers=self.headers, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"❌ Error al obtener historial: {e}", flush=True)
            return None
