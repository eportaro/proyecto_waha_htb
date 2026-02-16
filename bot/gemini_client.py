# gemini_client.py
from __future__ import annotations

import os
import re
import json
from typing import Any, Dict, Optional, List

from dotenv import load_dotenv

# Gemini es opcional: si no hay API KEY, el bot sigue con fallback determinista
try:
    import google.generativeai as genai
except Exception:
    genai = None

# Enums opcionales (SDKs nuevos). Si no existen, los manejamos con fallback.
try:
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except Exception:
    HarmCategory = None
    HarmBlockThreshold = None

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
# Modelos recomendados: "gemini-2.5-flash", "gemini-1.5-flash"
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.0")) # Temperatura baja para determinismo
MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "600"))
# Si quieres forzar safety explícito (solo si el SDK soporta enums):
# GEMINI_SAFETY_RELAXED=true → aplica umbral medio
USE_SAFETY = os.getenv("GEMINI_SAFETY_RELAXED", "false").lower() == "true"

if not API_KEY:
    print("⚠️ GOOGLE_API_KEY no configurada (modo básico sin IA)", flush=True)

if API_KEY and genai:
    try:
        genai.configure(api_key=API_KEY)
    except Exception as e:
        print(f"⚠️ No se pudo configurar Gemini: {e}", flush=True)


def _clean_json_block(s: str) -> str:
    """Limpia delimitadores de markdown y extrae el primer bloque JSON plausible."""
    if not s:
        return ""
    s = s.strip()
    # Eliminar bloques de código markdown
    s = re.sub(r"```json\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"```\s*", "", s)
    
    # Buscar el primer { y el último }
    start = s.find("{")
    end = s.rfind("}")
    
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    
    return s


def _safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
    """Parsea JSON de forma tolerante a errores comunes."""
    if not s:
        return None
    s_clean = _clean_json_block(s)
    try:
        return json.loads(s_clean)
    except Exception:
        # Intentos de reparación básicos
        s2 = s_clean
        s2 = s2.replace("\n", " ").replace("\r", " ")
        s2 = re.sub(r"(\w+):\s*'([^']*)'", r'"\1":"\2"', s2)  # key:'val'
        s2 = s2.replace("'", '"')
        s2 = s2.replace("True", "true").replace("False", "false").replace("None", "null")
        s2 = re.sub(r",\s*([\]}])", r"\1", s2)  # comas colgantes
        try:
            return json.loads(s2)
        except Exception:
            return None


def _mk_safety_settings():
    """
    Devuelve safety_settings compatibles con SDKs nuevos (enums).
    Si el SDK no soporta enums, devuelve None y NO pasamos safety_settings.
    """
    if not (HarmCategory and HarmBlockThreshold and USE_SAFETY):
        return None
    try:
        return {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }
    except Exception:
        # Ante cualquier incompatibilidad, no pasamos safety explícito
        return None


class GeminiClient:
    """Cliente de IA conversacional para el bot de RRHH (cálido + robusto)."""

    def __init__(self):
        self.model = None
        if API_KEY and genai:
            try:
                safety_settings = _mk_safety_settings()  # None si el SDK no soporta enums o no se pidió
                kwargs = {
                    "model_name": MODEL_NAME,
                    "generation_config": {
                        "temperature": TEMPERATURE,
                        "top_p": 0.9,
                        "max_output_tokens": MAX_TOKENS,
                        "response_mime_type": "application/json", # Forzar JSON mode si el modelo lo soporta
                    },
                    "system_instruction": (
                        "Eres \"Hermes ReclutaBot\", un asistente de reclutamiento automatizado de **Hermes Transportes Blindados**.\n\n"
                        "🎯 TU OBJETIVO PRINCIPAL:\n"
                        "Evaluar postulantes mediante preguntas estructuradas, filtrar si son aptos para continuar el proceso y:\n"
                        "- Si son APTOS → invitarlos a entrevista presencial o virtual.\n"
                        "- Si NO son APTOS → agradecer su interés y decir que su perfil será evaluado.\n\n"
                        "🚫 LÍMITES ESTRICTOS (GUARDRAILS):\n"
                        "1. Tu única función es la extracción de datos de postulantes y brindar información básica sobre la postulación.\n"
                        "2. SI el usuario pregunta sobre temas ajenos (matemáticas, clima, código, chistes, política), RECHAZA educadamente: "
                        "'Soy un asistente de Reclutamiento de Hermes. Mi función es ayudarte con tu postulación. ¿Continuamos?'.\n"
                        "3. NO inventes horarios ni cambies reglas.\n"
                        "4. Cuando se te pida extraer JSON, responde SOLO CON JSON."
                    ),
                }
                if safety_settings:
                    kwargs["safety_settings"] = safety_settings  # solo si seguro

                self.model = genai.GenerativeModel(**kwargs)

                print(
                    f"✅ Gemini inicializado: {MODEL_NAME} (temp={TEMPERATURE}, max={MAX_TOKENS})"
                    + (" con safety relajado" if safety_settings else " sin safety explícito"),
                    flush=True,
                )
            except Exception as e:
                print(f"❌ Error inicializando Gemini: {e}", flush=True)
                self.model = None
        else:
            print("⚠️ Gemini no disponible - operando con fallback determinista", flush=True)

    # ─────────────────────────────────────────────────────────────
    # Núcleo de generación (robusto ante cambios del SDK)
    # ─────────────────────────────────────────────────────────────
    def _generate(self, prompt: str) -> Optional[str]:
        """
        Genera texto con Gemini y maneja respuestas sin .text / candidates.
        Retorna str (posible JSON) o None si fue bloqueado o falló.
        """
        if not self.model:
            return None
        try:
            resp = self.model.generate_content(prompt)

            # 1) Camino feliz: atributo .text (puede lanzar si no hay parts)
            text = None
            try:
                text = getattr(resp, "text", None)
            except Exception:
                text = None
            if text:
                return text.strip()

            # 2) Analizar candidates y parts (SDKs recientes)
            cand = None
            if hasattr(resp, "candidates") and resp.candidates:
                cand = resp.candidates[0]
                # finish_reason puede ser enum/int/str; normalizamos
                fr = getattr(cand, "finish_reason", None)
                fr_val = str(fr).lower() if fr is not None else ""
                # Bloqueos por safety / listas
                if any(k in fr_val for k in ["safety", "blocklist", "prohibited", "spii"]):
                    print(
                        f"[Gemini] Bloqueado por finish_reason={fr}. "
                        f"prompt_feedback={getattr(resp, 'prompt_feedback', None)}",
                        flush=True,
                    )
                    return None

                content = getattr(cand, "content", None)
                if content and hasattr(content, "parts"):
                    texts: List[str] = []
                    for p in content.parts:
                        t = getattr(p, "text", None)
                        if t:
                            texts.append(t)
                    if texts:
                        return "\n".join(texts).strip()

            return None
        except Exception as e:
            error_msg = str(e).lower()
            print(f"[Gemini Error] {e}", flush=True)
            # Si la API key fue revocada/leaked, desactivar Gemini para no repetir calls
            if "leaked" in error_msg or "403" in error_msg or "invalid api key" in error_msg:
                print("[Gemini] API key inválida/revocada. Desactivando Gemini para esta sesión.", flush=True)
                self.model = None
            return None

    # ─────────────────────────────────────────────────────────────
    # Extracción + Validación (primero IA, luego fallback amable)
    # ─────────────────────────────────────────────────────────────
    def extract_and_validate(
        self,
        question_key: str,
        user_response: str,
        current_data: dict,
        conversation_history: list,
        available_positions: list | None = None,
    ) -> dict:
        """
        Devuelve:
        {
          "is_valid": bool,
          "extracted_data": dict,
          "bot_response": str
        }
        """
        # La IA es la primera capa
        if self.model:
            history_text = ""
            if conversation_history:
                for msg in conversation_history[-3:]:
                    role = "Usuario" if msg.get("role") == "user" else "Asistente"
                    history_text += f"{role}: {msg.get('message','')}\n"

            prompt = self._build_prompt(
                question_key, user_response, history_text, current_data, available_positions
            )
            
            if prompt:
                result = self._generate(prompt)
                print(
                    f"[DEBUG-IA] {question_key} - USER: {user_response}  | RAW: {result[:200] if result else ''}",
                    flush=True,
                )

                if result:
                    data = _safe_json_loads(result)
                    if data:
                        extracted = data.get("extracted_data", {})
                        is_valid = data.get("is_valid", False)
                        bot_response = data.get("bot_response")
                        
                        # Si la IA dice que es válido pero no extrajo nada, sospechoso.
                        if is_valid and not extracted and question_key not in ["disponibilidad", "secundaria", "dni", "licencia"]:
                             # Para booleanos puede ser válido y false, pero extracted debería tener la key.
                             pass

                        return {
                            "is_valid": is_valid,
                            "extracted_data": extracted,
                            "bot_response": bot_response,
                        }

                print("[DEBUG] IA no retornó JSON usable. Uso fallback determinista.", flush=True)

        # Fallback determinista (amable, entiende “sip/sep/ok/obvio/de una”, etc.)
        return self._fallback_extraction(question_key, user_response, current_data)

    def _build_prompt(
        self,
        question_key: str,
        user_response: str,
        history_text: str,
        current_data: dict,
        available_positions: list | None,
    ) -> Optional[str]:
        """Prompt específico por pregunta, exigiendo JSON puro."""
        
        base_prompt = f"""
CONTEXTO:
{history_text}

PREGUNTA ACTUAL: {question_key}
RESPUESTA USUARIO: "{user_response}"

OBJETIVO: Extraer la información en formato JSON estricto.
"""

        if question_key == "genero":
            return base_prompt + """
ENUMS PERMITIDOS: "M" (Masculino), "F" (Femenino), "O" (Otros).
Mapea "hombre", "varon" -> "M". "mujer", "dama" -> "F".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "genero": "M" | "F" | "O" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""

        if question_key == "tipo_documento":
            return base_prompt + """
ENUMS PERMITIDOS: "dni", "ce".
Mapea "carnet de extranjeria", "c.e.", "extranjero" -> "ce".
Mapea "documento nacional", "dni azul", "dni electronico" -> "dni".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "tipo_documento": "dni" | "ce" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""

        if question_key == "modalidad":
            return base_prompt + """
ENUMS PERMITIDOS: "tiempo_completo", "medio_tiempo", "intermitente".
Mapea "full time", "completo", "todo el dia" -> "tiempo_completo".
Mapea "part time", "medio", "mitad" -> "medio_tiempo".
Mapea "por dias", "eventual" -> "intermitente".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "modalidad_trabajo": "tiempo_completo" | "medio_tiempo" | "intermitente" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""

        if question_key == "licencia_tipo":
            return base_prompt + """
ENUMS PERMITIDOS: "A1_AIIa", "AIIb_AIIIa_AIIIb_AIIIc", "BIIb", "sin_licencia".
Mapea "a1", "a2a", "particular" -> "A1_AIIa".
Mapea "a2b", "a3", "a3c", "profesional" -> "AIIb_AIIIa_AIIIb_AIIIc".
Mapea "moto", "b2", "bii" -> "BIIb".
Mapea "no tengo", "ninguna" -> "sin_licencia".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "licencia_cat": "ENUM" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""

        if question_key == "medio_captacion":
            return base_prompt + """
ENUMS PERMITIDOS: "tiktok", "canal_whatsapp", "correo", "volante", "qr", "facebook", "referido", "instagram", "otros".
Mapea "vi un video", "tik tok" -> "tiktok".
Mapea "me llego un mail", "email" -> "correo".
Mapea "un amigo", "conocido" -> "referido".
Mapea "fb", "face" -> "facebook".
Mapea "insta", "ig" -> "instagram".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "medio_captacion": "ENUM" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""

        if question_key == "numero_documento":
            return base_prompt + """
OBJETIVO: Extraer el número de documento.
REGLA CRÍTICA:
- Si es DNI, DEBE tener EXACTAMENTE 8 dígitos. Si tiene más o menos, es INVÁLIDO.
- Si es CE (Carné de Extranjería), puede tener más de 8 dígitos.
- Si no se especifica tipo, asume DNI (8 dígitos).

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "numero_documento": "12345678" },
  "bot_response": "mensaje de error si la longitud es incorrecta"
}
"""

        if question_key == "telefono":
            return base_prompt + """
OBJETIVO: Extraer número de celular.
REGLA CRÍTICA: DEBE tener EXACTAMENTE 9 dígitos.
Si tiene 8 o 10+, es INVÁLIDO.

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "telefono_contacto": "987654321" },
  "bot_response": "mensaje de error si no tiene 9 dígitos"
}
"""

        if question_key == "horario_entrevista":
            return base_prompt + """
ENUMS PERMITIDOS: "manana_9_13", "tarde_15_17".
Mapea "mañana", "1", "9am", "temprano" -> "manana_9_13".
Mapea "tarde", "2", "3pm", "luego" -> "tarde_15_17".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "horario_entrevista": "ENUM" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""
        if question_key == "secundaria":
            return base_prompt + """
JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "secundaria": boolean },
  "bot_response": "mensaje de error si no es valido, o null"
}
NOTA: Si el usuario menciona estudios superiores (universidad, instituto, maestría, doctorado, bachiller, egresado), asume "secundaria": true.
"""

        if question_key == "trabajo_hermes":
            return base_prompt + """
JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "ha_trabajado_en_hermes": boolean },
  "bot_response": "mensaje de error si no es valido, o null"
}
NOTA:
- Si dice "sí", "claro", "por supuesto", "hace tiempo", "antiguamente", "en el 2010", "hace unos años", "ya trabajé", asume TRUE.
- Si dice "no", "nunca", "primera vez", asume FALSE.
"""

        if question_key == "lugar_residencia":
            return base_prompt + """
OBJETIVO: Clasificar si el usuario vive en "Lima" o "Provincia".
Si menciona un distrito de Lima (Surco, Miraflores, SJL, Comas, etc.), extrae "Lima".
Si menciona una ciudad de provincia (Trujillo, Arequipa, etc.), extrae "Provincia".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "lugar_residencia": "Lima" | "Provincia", "origen": "lima" | "provincia" },
  "bot_response": "mensaje de error si no es claro, o null"
}
"""

        if question_key == "horario_entrevista":
            return base_prompt + """
OBJETIVO: Extraer una HORA específica en formato HH:MM (24h).
Si el usuario dice "10am", extrae "10:00".
Si dice "4pm", extrae "16:00".
Si dice "10:30", extrae "10:30".

JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "horario_entrevista": "HH:MM" },
  "bot_response": "mensaje de error si no es valido (debe ser hora concreta), o null"
}
"""
        
        # Default genérico para otros campos si se usa IA
        return base_prompt + """
JSON ESPERADO:
{
  "is_valid": boolean,
  "extracted_data": { "campo": "valor" },
  "bot_response": "mensaje de error si no es valido, o null"
}
"""

    # ─────────────────────────────────────────────────────────────
    # Fallback determinista (sin IA) — con tono amable
    # ─────────────────────────────────────────────────────────────
    def _fallback_extraction(self, key: str, response: str, data: dict) -> dict:
        """Fallback contextual cuando Gemini no está disponible."""
        # Mensajes de reprompt específicos por pregunta
        reprompt_messages = {
            "genero": "Por favor responde: Masculino, Femenino u Otros.",
            "tipo_documento": "Responde DNI o Carné de Extranjería.",
            "numero_documento": "El DNI debe tener exactamente 8 dígitos.",
            "telefono": "El teléfono debe tener exactamente 9 dígitos.",
            "correo": "Ingresa un correo válido (ej. usuario@dominio.com).",
            "secundaria": "¿Secundaria Completa o Incompleta?",
            "trabajo_hermes": "¿Has trabajado en Hermes? (Sí / No)",
            "modalidad": "Responde con el número:\n1. Tiempo Completo\n2. Medio Tiempo\n3. Intermitente por días",
            "lugar_residencia": "¿Lima o Provincia?",
            "licencia": "¿Tienes licencia de conducir? (Sí / No)",
            "licencia_tipo": "Indica la categoría (A1, A2B, BII, etc.).",
            "puesto": "Elige una opción del menú (responde con el número).",
            "disponibilidad": "¿Disponibilidad inmediata? (Sí / No)",
            "medio_captacion": "Responde con el número (1-9).",
            "horario_entrevista": "Indica una hora entre 9am-1pm o 3pm-5pm (ej. 10:00 am).",
        }
        msg = reprompt_messages.get(key)
        return {
            "is_valid": False,
            "extracted_data": {},
            "bot_response": msg,
        }

    # ─────────────────────────────────────────────────────────────
    # Respuesta final (cálida)
    # ─────────────────────────────────────────────────────────────
    def generate_final_response(
        self,
        candidate_data: dict,
        is_apto: bool,
        rejection_reasons: list,
        company_info: dict,
    ) -> str:
        if is_apto:
            puesto = candidate_data.get("puesto_name", "el puesto")
            return (
                f"¡Excelente! Has sido *pre-aprobado* para **{puesto}**. 🎉\n\n"
                "Puedes acercarte a nuestra oficina para entrevista presencial:\n"
                "📍 *Av. Prol. Huaylas 1720, Chorrillos*\n"
                "🕘 *Horarios:* 9:00 a.m. o 2:00 p.m.\n\n"
                "Al llegar, menciona que fuiste pre-aprobado por el asistente virtual. ¡Te esperamos! 🙌"
            )
        else:
            return (
                "Gracias por completar tu postulación. 🙌\n\n"
                "Tu información ha sido registrada y será revisada por nuestro equipo de selección. "
                "Si tu perfil se ajusta a las vacantes disponibles, nos pondremos en contacto contigo "
                "por este medio. ✅"
            )

    # ─────────────────────────────────────────────────────────────
    # Conversación libre (post-completado)
    # ─────────────────────────────────────────────────────────────
    def respuesta_conversacional(self, user_message: str, context: str, company_info: dict) -> str:
        if not self.model:
            return (
                "Gracias por escribirnos. Tu información ya fue registrada. "
                "Nuestro equipo se comunicará contigo a la brevedad. 🙏"
            )

        prompt = f"""Eres un asistente de RRHH amable de {company_info.get('nombre','la empresa')}.
CONTEXTO DEL CANDIDATO:
{context}

MENSAJE DEL USUARIO: "{user_message}"

INSTRUCCIONES:
1. Responde brevemente y con calidez.
2. Si el usuario pide cambiar su horario de entrevista:
   - Si ya tiene uno agendado, dile amablemente que por ahora queda fijo, pero que RRHH lo contactará si es necesario ajustar.
   - NO inventes que lo has cambiado.
3. Si pide volver a postular:
   - Explica que ya tiene una postulación registrada.
4. NO des detalles técnicos ni menciones "JSON".

FORMATO DE RESPUESTA (JSON OBLIGATORIO):
{{
  "response": "tu respuesta en texto plano aquí"
}}
"""
        result = self._generate(prompt)
        if result:
            data = _safe_json_loads(result)
            if data and "response" in data:
                return data["response"]
        
        return (
            "Gracias por escribirnos. Tu información ya fue registrada. "
            "Nuestro equipo se comunicará contigo a la brevedad. 🙏"
        )
