# ai_bot.py
from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from difflib import get_close_matches

# --------------------------------------------------------------------------------
# Imports flexibles para GeminiClient y Database
# --------------------------------------------------------------------------------
try:
    from .gemini_client import GeminiClient  # dentro de /bot
except Exception:
    try:
        from gemini_client import GeminiClient
    except Exception:
        GeminiClient = None  # opcional

try:
    from services.database import Database  # dentro de /services
except Exception:
    try:
        from database import Database
    except Exception:
        Database = None  # fallback opcional

# --------------------------------------------------------------------------------
# Parámetros (ajustables por variables de entorno)
# --------------------------------------------------------------------------------
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
COOLDOWN_HOURS = int(os.getenv("COOLDOWN_HOURS", "24"))

# Catálogo de puestos (ids estables)
PUESTOS: List[Dict[str, Any]] = [
    {"id": 1, "name": "Agentes de Seguridad Chorrillos"},
    {"id": 2, "name": "Agentes de Traslado de Valores Chorrillos"},
    {"id": 3, "name": "Agentes de Seguridad para Bancos"},
    {"id": 4, "name": "Agentes de Seguridad Provincia"},
    {"id": 5, "name": "Operarios de Carga y Descarga"},
    {"id": 6, "name": "Cajeros (Atención al Cliente)"},
    {"id": 7, "name": "Coordinadores / Encargados de Caja"},
    {"id": 8, "name": "Conductores / Choferes (A1 - A2B)"},
    {"id": 9, "name": "Motorizados BII"},
    {"id": 10, "name": "Operarios de Limpieza"},
    {"id": 11, "name": "Despachadores"},
    {"id": 12, "name": "Agentes de Seguridad - Minería"},
    {"id": 13, "name": "Supervisores Operativos - Minería"},
    {"id": 14, "name": "Técnico Electrónico"},
    {"id": 15, "name": "Mecánico Automotriz"},
    {"id": 16, "name": "Técnico Electricista"},
    {"id": 17, "name": "Digitadores"},
    {"id": 18, "name": "Otros"},
]

# Mapeo de Ubicación por Puesto (Regla de Negocio)
PUESTO_UBICACION = {
    1: "Lima",       # Agentes de Seguridad Chorrillos
    2: "Lima",       # Agentes de Traslado de Valores Chorrillos
    3: "Ambos",      # Agentes de Seguridad para Bancos
    4: "Provincia",  # Agentes de Seguridad Provincia
    5: "Ambos",      # Operarios de Carga y Descarga
    6: "Ambos",      # Cajeros (Atención al Cliente)
    7: "Lima",       # Coordinadores / Encargados de Caja
    8: "Lima",       # Conductores / Choferes (A1 - A2B)
    9: "Lima",       # Motorizados BII
    10: "Lima",      # Operarios de Limpieza
    11: "Lima",      # Despachadores
    12: "Provincia", # Agentes de Seguridad - Minería Trujillo
    13: "Provincia", # Supervisores Operativos - Minería Trujillo
    14: "Lima",      # Técnico Electrónico
    15: "Lima",      # Mecánico Automotriz
    16: "Lima",      # Técnico Electricista
    17: "Lima",      # Digitadores
    18: "Ambos",     # Otros
}

# Mapeo rápido (sólo como “piso” cuando falle IA)
PUESTOS_KEYWORDS = {
    "conductor": 8,
    "chofer": 8,
    "motorizado": 9,
    "bii": 9,
    "seguridad": 3,  # por defecto Bank Security
    "cajero": 6,
    "limpieza": 10,
    "operario": 5,
    "carga": 5,
    "descarga": 5,
    "digitador": 17,
    "coordinador": 7,
    "encargado": 7,
    "supervisor": 13,
    "mineria": 12,
    "minería": 12,
    "provincia": 4,
}

# --------------------------------------------------------------------------------
# Utilidades de menú de puestos e intención de inicio
# --------------------------------------------------------------------------------
def _build_puestos_menu_text(include_header: bool = True) -> str:
    """
    Construye el menú numerado de puestos (1–18) en texto plano.
    """
    lines: List[str] = []
    if include_header:
        lines.append(
            "¡Genial! Para empezar, elige el puesto al que deseas postular.\n"
            "Responde solo con el *número* de la opción:\n"
        )
    for p in PUESTOS:
        lines.append(f"{p['id']}. {p['name']}")
    return "\n".join(lines)


def _detect_start_intent(text: str) -> bool:
    """
    Detecta si el usuario quiere iniciar su postulación.
    """
    tn = _norm_text(text)
    if not tn:
        return False

    start_phrases = {
        "empezar",
        "empieza",
        "iniciar",
        "comenzar",
        "quiero postular",
        "deseo postular",
        "quiero postularme",
        "postular",
        "postulacion",
        "postulación",
        "quiero trabajar",
        "deseo trabajar",
        "quiero un trabajo",
        "empesar",
    }

    if any(phrase in tn for phrase in start_phrases):
        return True

    short_yes = {"si", "sí", "claro", "dale", "vamos", "listo"}
    if any(w in tn.split() for w in short_yes):
        return True

    return False

# --------------------------------------------------------------------------------
# Utilidades de normalización y heurísticas (secundarias)
# --------------------------------------------------------------------------------
def _norm_text(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s


def _extract_int(s: str) -> Optional[int]:
    m = re.search(r"\b(\d{1,2})\b", s)
    return int(m.group(1)) if m else None


def _detect_location(s: str) -> Optional[str]:
    sx = _norm_text(s)
    if "lima" in sx:
        return "lima"
    provincia_markers = {
        "provincia",
        "trujillo",
        "arequipa",
        "cusco",
        "piura",
        "chiclayo",
        "tacna",
        "ica",
        "pucallpa",
        "tarapoto",
        "huancayo",
        "cajamarca",
        "puno",
        "madre de dios",
        "ayacucho",
        "huanuco",
        "loreto",
        "tumbes",
        "ancash",
        "apurimac",
        "moquegua",
        "ucayali",
        "pasco",
        "junin",
    }
    if any(w in sx for w in provincia_markers):
        return "provincia"
    return None


def _detect_licencia_categoria(s: str) -> Optional[str]:
    """
    Detecta categorías como A1, A2, A2A, A2B, A3C, BII en frases tipo:
    "Tengo la A2", "Licencia A2B", etc.
    """
    sx = _norm_text(s)
    # No eliminamos espacios para que \b funcione bien con " a2"
    m = re.search(r"\b(a[123](?:a|b|c)?|bii)\b", sx)
    return m.group(1).upper().replace(" ", "").replace("-", "") if m else None


def _puesto_from_text(s: str) -> Optional[Dict[str, Any]]:
    """
    Intenta mapear texto libre a un puesto específico.
    Devuelve None si no encuentra match claro (no fuerza 'Otros').
    """
    sx = _norm_text(s)

    # Caso explícito "otros"
    if "otro" in sx or "otros" in sx:
        match = next((p for p in PUESTOS if p["id"] == 18), None)
        if match:
            return {"puesto_id": match["id"], "puesto_name": match["name"]}

    # Keywords directas
    for key, pid in PUESTOS_KEYWORDS.items():
        if key in sx:
            match = next((p for p in PUESTOS if p["id"] == pid), None)
            if match:
                return {"puesto_id": match["id"], "puesto_name": match["name"]}

    # Caso particular seguridad + provincia
    if "seguridad" in sx and "provincia" in sx:
        match = next((p for p in PUESTOS if p["id"] == 4), None)
        if match:
            return {"puesto_id": match["id"], "puesto_name": match["name"]}

    # Si no se reconoce, devolvemos None para que IA o repregunta entren
    return None


# --------------------------------------------------------------------------------
# Clase principal (modelo híbrido: reglas primero, IA cuando se sale del carril)
# --------------------------------------------------------------------------------
class AIBot:
    """
    Bot conversacional para preselección de personal con enfoque híbrido:
    1) Reglas deterministas suaves para casos esperados (rápido y barato),
    2) IA (Gemini) cuando la respuesta se sale del carril o es ambigua,
    3) Reglas deterministas finales para la decisión de aptitud (auditables).
    """

    def __init__(self, db: Any = None, gemini: Any = None) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.gemini = gemini if gemini is not None else (GeminiClient() if GeminiClient else None)
        self.db = db if db is not None else (Database() if Database else None)

        self.company_info = {
            "nombre": "Hermes Transportes Blindados",
            "descripcion": "Empresa líder en transporte de valores y seguridad.",
            "valores": "Compromiso, seguridad, confiabilidad y profesionalismo.",
        }

        # Flujo extendido de preguntas (22 pasos + entrevista condicional)
        self.questions_flow: List[str] = [
            "autorizacion_datos", # Nuevo paso 0
            "nombre",
            "apellidos",
            "edad",
            "genero",
            "tipo_documento",
            "numero_documento",
            "telefono",
            "correo",
            "secundaria",
            "trabajo_hermes",
            "modalidad",
            "distrito",
            "lugar_residencia", # Lima/Provincia
            "ciudad",           # Solo si Provincia
            "licencia",         # ¿Tiene licencia?
            "licencia_tipo",    # Solo si tiene
            "puesto",
            "puesto_otros",     # Solo si Puesto == Otros
            "puesto_mineria_sucursal", # Nuevo: Solo si Puesto == 12 o 13
            "disponibilidad",
            "medio_captacion",
            "medio_captacion_otro", # Solo si Medio == Otros
            "confirmacion_entrevista",   # Nuevo: Solo si APTO, reemplaza a horario_entrevista
        ]

    # ------------- Gestión de sesiones -------------
    def _init_session(self, chat_id: str) -> None:
        self.sessions[chat_id] = {
            "step": 0,
            "data": {
                # Campos básicos
                "puesto_id": None,
                "puesto_name": None,
                "edad": None,
                "origen": None, # Legacy (mapeado desde lugar_residencia)
                "destino": None, # Legacy (mapeado desde puesto/lugar)
                "secundaria": None,
                "dni": None, # Legacy (mapeado desde tipo_documento)
                "licencia": None,
                "licencia_cat": None,
                "disponibilidad": None,

                # Nuevos campos
                "nombres": None, # Temp
                "apellidos": None, # Temp
                "nombre_completo": None,
                "genero": None,
                "tipo_documento": None,
                "numero_documento": None,
                "correo_electronico": None,
                "telefono_contacto": None,
                "ha_trabajado_en_hermes": None,
                "modalidad_trabajo": None,
                "distrito_residencia": None,
                "ciudad_residencia": None, # Si es provincia
                "medio_captacion": None,
                "medio_captacion_otro": None,
                "puesto_otros_detalle": None,
                "horario_entrevista": None,
                "fecha_entrevista": None, # Nuevo
                "confirmacion_asistencia": None, # Nuevo
                "autorizacion_datos": None,
            },
            "raw_answers": {},
            "conversation_history": [],
            "retry_count": 0,
            "last_answer_snapshot": None,
            "same_answer_count": 0,
            "last_activity": datetime.now(),
            "completed": False,
            "completion_time": None,
            "final_response": None,   # última respuesta de cierre enviada al candidato
            "is_apto": None,          # resultado de la evaluación determinista
        }

    def _reset_session(self, chat_id: str) -> None:
        self._init_session(chat_id)

    def _is_session_expired(self, chat_id: str) -> bool:
        s = self.sessions.get(chat_id)
        if not s:
            return True
        return (datetime.now() - s["last_activity"]) > timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    def _can_restart(self, chat_id: str) -> bool:
        s = self.sessions.get(chat_id)
        if not s or not s.get("completion_time"):
            return True
        return (datetime.now() - s["completion_time"]) > timedelta(hours=COOLDOWN_HOURS)

    def _update_activity(self, chat_id: str) -> None:
        if chat_id in self.sessions:
            self.sessions[chat_id]["last_activity"] = datetime.now()

    def _add_to_history(self, chat_id: str, role: str, message: str) -> None:
        if chat_id not in self.sessions:
            return
        hist = self.sessions[chat_id]["conversation_history"]
        hist.append({"role": role, "message": message})
        if len(hist) > 10:
            self.sessions[chat_id]["conversation_history"] = hist[-10:]

    # ------------- Núcleo de procesamiento -------------
    def process(self, chat_id: str, text: str) -> str:
        if not text or not text.strip():
            return "¿Me puedes escribir tu consulta o respuesta? ??"

        text = text.strip()
        text_norm = _norm_text(text)
        start_intent = _detect_start_intent(text)

        # Comandos globales
        if text_norm in {"ayuda", "help", "menu"}:
            return (
                "?? *Comandos:*\n"
                "• *empezar* — iniciar postulación\n"
                "• *reiniciar* — reiniciar proceso\n"
                "• *estado* — ver progreso"
            )

        # Crear/renovar sesión
        if chat_id not in self.sessions or self._is_session_expired(chat_id):
            self._init_session(chat_id)
            if start_intent:
                self.sessions[chat_id]["step"] = 1
                return self._ask_next(self.sessions[chat_id]) # Pregunta 1: Nombre

            return (
                f"¡Hola! ?? Soy el asistente virtual de *{self.company_info['nombre']}*.\n"
                "Para iniciar tu postulación, escribe *empezar* o *quiero postular*."
            )

        s = self.sessions[chat_id]
        self._update_activity(chat_id)
        self._add_to_history(chat_id, "user", text)

        # Post-completado
        if s["completed"]:
            if text_norm in {"reiniciar", "empezar", "nuevo"}:
                if self._can_restart(chat_id):
                    self._reset_session(chat_id)
                    s = self.sessions[chat_id]
                    s["step"] = 1
                    return self._ask_next(s)
                hours_left = int(COOLDOWN_HOURS - (datetime.now() - s["completion_time"]).total_seconds() / 3600)
                return f"Ya completaste tu postulación. Podrás volver a postular en {max(hours_left, 0)} horas."

            if "estado" in text_norm:
                return s.get("final_response") or "Tu postulación está registrada."

            # Chat libre post-postulación
            if self.gemini:
                # Construir contexto rico
                ctx_parts = []
                if s.get("is_apto"):
                    ctx_parts.append("Estado: APTO (Pre-aprobado).")
                    horario = s["data"].get("horario_entrevista")
                    if horario:
                        ctx_parts.append(f"Entrevista agendada: {horario}.")
                    else:
                        ctx_parts.append("Entrevista: Pendiente o no seleccionada.")
                else:
                    ctx_parts.append("Estado: NO APTO (Registrado para futura consideración).")

                ctx_parts.append(f"Fecha postulación: {s.get('completion_time')}")
                context_str = "\n".join(ctx_parts)

                return self.gemini.respuesta_conversacional(text, context_str, self.company_info)
            return "Gracias por tu interés. Ya tenemos tus datos registrados. ??"

        # Estado durante sesión
        if text_norm == "estado":
            step = s["step"]
            total = len(self.questions_flow)
            return f"?? Progreso: paso {step} de {total} (aprox)."

        if text_norm.startswith("reiniciar"):
            self._reset_session(chat_id)
            s = self.sessions[chat_id]
            s["step"] = 1
            return self._ask_next(s)

        # Si aún no empezó (step 0)
        if s["step"] == 0:
            if start_intent:
                s["step"] = 1
                return self._ask_next(s)

            if self.gemini:
                return self.gemini.respuesta_conversacional(
                    text, "Invita al usuario a escribir 'empezar' para postular.", self.company_info
                )
            return "Escribe *empezar* para iniciar tu postulación. ??"

        # Procesar respuesta actual
        current_key = self.questions_flow[s["step"] - 1]
        s["raw_answers"][current_key] = text

        # Anti-loop
        if s["last_answer_snapshot"] == text_norm:
            s["same_answer_count"] += 1
        else:
            s["same_answer_count"] = 0
            s["last_answer_snapshot"] = text_norm

        # Validación
        valid = False
        normalized_data: Dict[str, Any] = {}
        need_clarify_msg: Optional[str] = None

        # 1. Determinista
        det_valid, det_data, det_msg = self._validate_and_extract_soft(current_key, text, s["data"])
        if det_data:
            normalized_data.update(det_data)
        if det_valid:
            valid = True
        else:
            need_clarify_msg = det_msg

        # 2. IA (si falla determinista)
        if not valid and self.gemini:
            try:
                # Contexto extra para IA (opciones de enums)
                extra_context = ""
                if current_key == "medio_captacion":
                    extra_context = "Opciones: tiktok, canal_whatsapp, correo, volante, qr, facebook, referido, instagram, otros"

                extraction = self.gemini.extract_and_validate(
                    question_key=current_key,
                    user_response=text,
                    current_data=s["data"],
                    conversation_history=s["conversation_history"][-4:],
                    available_positions=[p["name"] for p in PUESTOS] if current_key == "puesto" else [],
                )
                if extraction and extraction.get("extracted_data"):
                    normalized_data.update(extraction["extracted_data"])
                    # Mapeo manual de campos extraídos por IA si es necesario
                    if "licencia_cat" in extraction["extracted_data"]:
                         normalized_data["licencia"] = True

                    # -------------------------------------------------------------
                    # VALIDACIÓN POST-IA (Firewall contra alucinaciones)
                    # -------------------------------------------------------------
                    # DNI Estricto
                    if "numero_documento" in normalized_data:
                        ndoc = normalized_data["numero_documento"]
                        # Si es DNI (o no especificado tipo), debe ser 8
                        # Si es CE, permitimos más.
                        tipo = s["data"].get("tipo_documento") or normalized_data.get("tipo_documento")
                        if tipo != "ce":
                            # FIX 1: Agregar chequeo de None antes de len()
                            if not ndoc:
                                normalized_data.pop("numero_documento")
                            elif len(ndoc) != 8:
                                valid = False
                                need_clarify_msg = "El DNI debe tener exactamente 8 dígitos (IA detectó otro formato)."
                                normalized_data.pop("numero_documento") # Invalidar

                    # Teléfono Estricto
                    if "telefono_contacto" in normalized_data:
                        tfon = normalized_data["telefono_contacto"]
                        # FIX 2: Agregar chequeo de None antes de len()
                        if not tfon:
                            normalized_data.pop("telefono_contacto")
                        elif len(tfon) != 9:
                            valid = False
                            need_clarify_msg = "El teléfono debe tener exactamente 9 dígitos (IA detectó otro formato)."
                            normalized_data.pop("telefono_contacto") # Invalidar
                    # -------------------------------------------------------------

                valid = bool(extraction and extraction.get("is_valid")) and valid
                if not valid and not need_clarify_msg:
                    need_clarify_msg = (extraction or {}).get("bot_response")
            except Exception as e:
                print(f"[AIBot] Gemini error: {e}", flush=True)

        # 3. Reintentos y Manejo de Errores (Humanizado)
        if not valid:
            # -[ SOFT RETRY LOGIC FOR AGE ]------------------------
            # Si es la 2da vez que falla en edad, lo dejamos pasar con lo que haya (o 0)
            if current_key == "edad" and s["retry_count"] >= 1:
                # Recuperar cualquier int que hayamos podido sacar, o el raw
                print(f"[AIBot] Soft Retry triggered for Age. Accepting input: {text}")
                # Intentar re-extract simple
                forced_age = _extract_int(text)
                if forced_age:
                     s["data"]["edad"] = forced_age
                else:
                     # Si es texto puro ("tengo quince"), ya intentamos IA antes.
                     # Si falló, guardamos 0 o null para analizar luego manualmente si se desea.
                     # Pero para no bloquear, avanzamos.
                     pass

                # Forzar avance
                s["retry_count"] = 0
                s["step"] += 1
                return self._ask_next(s)
            # -----------------------------------------------------

            s["retry_count"] += 1
            if s["same_answer_count"] >= 2:
                # Forzar avance si se atasca repitiendo lo mismo
                s["retry_count"] = 0
                s["step"] += 1
                return self._ask_next(s)

            # GENERACIÓN DINÁMICA DE ERROR CON GEMINI
            # En lugar de solo "El DNI debe tener 8 dígitos", le pedimos a Gemini que lo diga amable.
            clarify = need_clarify_msg or "No entendí tu respuesta."

            if self.gemini and need_clarify_msg:
                try:
                    # Prompt para parafrasear el error amablemente
                    error_ctx = (
                        f"El usuario respondió: '{text}'.\n"
                        f"La validación falló con este error técnico: '{need_clarify_msg}'.\n"
                        "Actúa como reclutador humano de Hermes Transportes Blindados.\n"
                        "Cuando el usuario cometa un error:\n"
                        "- Responde de forma breve, clara y natural.\n"
                        "- Empieza directamente con la explicación del problema, como si la conversación ya estuviera en curso.\n"
                        "- NO inicies con saludos formales (Hola, Buen día, etc.).\n"
                        "- Usa un tono humano y cercano, no robótico ni autoritario.\n"
                        "- Pide el dato nuevamente con tacto."
                    )
                    human_error = self.gemini.respuesta_conversacional(text, error_ctx, self.company_info)
                    if human_error:
                        clarify = human_error
                except Exception as e:
                    print(f"Error generando error dinámico: {e}")

            self._add_to_history(chat_id, "assistant", clarify)
            return clarify

        # Respuesta válida
        s["retry_count"] = 0
        if normalized_data:
            s["data"].update(normalized_data)

        # Lógica de transición (saltos condicionales)
        next_step_idx = self._get_next_step_index(s["step"], s["data"])

        # Si terminamos el flujo
        if next_step_idx >= len(self.questions_flow):
            return self._finalize_session(chat_id, s)

        s["step"] = next_step_idx + 1 # step es 1-based
        return self._ask_next(s)

    def _get_next_step_index(self, current_step_1based: int, data: Dict[str, Any]) -> int:
        """
        Determina el índice (0-based) de la siguiente pregunta, saltando las irrelevantes.
        """
        idx = current_step_1based

        next_idx = current_step_1based

        while next_idx < len(self.questions_flow):
            q_key = self.questions_flow[next_idx]

            # Condicionales
            if q_key == "numero_documento":
                # Si ya tenemos el número (por inferencia en paso anterior), saltamos
                if data.get("numero_documento"):
                    next_idx += 1
                    continue

            if q_key == "ciudad":
                # Solo si lugar_residencia es provincia
                if data.get("origen") != "provincia":
                    next_idx += 1
                    continue

            if q_key == "licencia_tipo":
                if not data.get("licencia"):
                    next_idx += 1
                    continue

            if q_key == "puesto_otros":
                # Solo si puesto_id es 18 (Otros)
                if data.get("puesto_id") != 18:
                    next_idx += 1
                    continue

            if q_key == "puesto_mineria_sucursal":
                if data.get("puesto_id") not in [12, 13]:
                    next_idx += 1
                    continue

            if q_key == "medio_captacion_otro":
                if data.get("medio_captacion") != "otros":
                    next_idx += 1
                    continue

            if q_key == "confirmacion_entrevista":
                # Solo si es APTO. Evaluamos aptitud preliminar aquí.
                es_apto, _ = self._evaluate_aptitud(data)
                if not es_apto:
                    next_idx += 1 # Saltamos entrevista si no es apto
                    continue

            # Si no se salta, este es el siguiente
            break

        return next_idx

    def _ask_next(self, s: Dict[str, Any]) -> str:
        step_idx = s["step"] - 1
        if step_idx >= len(self.questions_flow):
            return "Proceso finalizado."

        key = self.questions_flow[step_idx]
        msg = ""

        if key == "autorizacion_datos":
            msg = (
                "?? *FORMATO DE CONSENTIMIENTO DE DATOS PERSONALES*\n\n"
                "Autorizo a HERMES TRANSPORTES BLINDADOS S.A. a tratar mis datos personales sensibles (antecedentes policiales, penales, judiciales, historial crediticio) "
                "para evaluar mi idoneidad en el proceso de selección, y a conservar mi CV por 6 meses. "
                "Puede ejercer sus derechos ARCO en protecciondatospersonales@hermes.com.pe.\n\n"
                "¿Autorizas el tratamiento de tus datos? (Responde *Sí* o *Acepto* para continuar)"
            )
        elif key == "nombre":
            msg = (
                "? Gracias. A continuación, iniciaremos un cuestionario de aprox. 20 preguntas como pre-entrevista de trabajo. "
                "Por favor asegúrate de completarlas todas correctamente.\n\n"
                "1) Por favor, indícame tus *Nombres* (sin apellidos)."
            )
        elif key == "apellidos":
            msg = "2) Ahora indícame tus *Apellidos*."
        elif key == "edad":
            msg = "3) ¿Qué *edad* tienes?"
        elif key == "genero":
            msg = "4) ¿Cuál es tu género? (Masculino / Femenino / Otros)"
        elif key == "tipo_documento":
            msg = "5) ¿Tipo de Documento de Identidad? (DNI / Carné de Extranjería)"
        elif key == "numero_documento":
            msg = "6) Indícame tu *Número de Documento*."
        elif key == "telefono":
            msg = "7) Bríndame un *Teléfono de Contacto*."
        elif key == "correo":
            msg = "8) ¿Cuál es tu *Correo electrónico*?"
        elif key == "secundaria":
            msg = "9) ¿Grado de instrucción? (Secundaria Completa / Secundaria Incompleta)"
        elif key == "trabajo_hermes":
            msg = "10) ¿Has trabajado en Hermes anteriormente? (Sí / No)"
        elif key == "modalidad":
            msg = "11) Indica la modalidad de trabajo elegida (responde con el número):\n1. Tiempo Completo\n2. Medio Tiempo\n3. Intermitente por días"
        elif key == "distrito":
            msg = "12) Indica el *distrito* en donde vives."
        elif key == "lugar_residencia":
            msg = "13) Indica tu lugar de residencia (Lima / Provincia)."
        elif key == "ciudad":
            msg = "14) Indica el *nombre de la provincia* de residencia."
        elif key == "licencia":
            msg = "15) ¿Cuentas con Licencia de Conducir? (Sí / No)"
        elif key == "licencia_tipo":
            msg = "16) Indica el tipo de licencia (A1, A2B, BII, etc.)."
        elif key == "puesto":
            msg = "17) Indica el puesto al que postulas:\n" + _build_puestos_menu_text(include_header=False)
        elif key == "puesto_otros":
            msg = "18) Especifica el puesto al que deseas postular."
        elif key == "puesto_mineria_sucursal":
            msg = "Elige Sucursal:\n1. Arequipa\n2. Trujillo\n3. Huanuco\n4. Cusco\n5. Otros"
        elif key == "disponibilidad":
            msg = "19) ¿Cuentas con disponibilidad inmediata? (Sí / No)"
        elif key == "medio_captacion":
            msg = ("20) ¿Por qué medio te enteraste de nuestras ofertas? (Responde con el número)\n"
                   "1. Tik Tok\n2. Canal de Whatsapp\n3. Correo\n4. Volante\n5. QR\n6. Facebook\n7. Referidos\n8. Instagram\n9. Otros")
        elif key == "medio_captacion_otro":
            msg = "Por favor especifica el medio por el cual te enteraste."
        elif key == "confirmacion_entrevista":
            # Calcular fecha con AFORO y DÍAS HÁBILES
            fecha_iso, dia_esp, fecha_fmt_short = self._get_next_valid_slot()

            # Guardamos la fecha propuesta en sesión temporal data por si confirma
            s["data"]["propuesta_fecha"] = fecha_iso

            msg = (
                "?? ¡Felicidades! Cumples con los requisitos preliminares.\n\n"
                f"Queremos invitarte a una evaluación presencial el día *{dia_esp} {fecha_fmt_short} a las 08:30 AM*.\n"
                "Será un *Full Day* donde realizaremos exámenes médicos, pruebas físicas y evaluaciones psicológicas.\n\n"
                "¿Nos confirmas tu asistencia? (Sí / No)"
            )

        return msg

    def _finalize_session(self, chat_id: str, s: Dict[str, Any]) -> str:
        s["completed"] = True
        s["completion_time"] = datetime.now()

        es_apto, razones = self._evaluate_aptitud(s["data"])
        s["is_apto"] = es_apto

        # Guardar en DB
        if self.db and hasattr(self.db, "save_postulante"):
            self.db.save_postulante(chat_id, s)

        final_msg = ""
        if es_apto:
            # Mensaje de éxito si confirmó
            confirmed = s["data"].get("confirmacion_asistencia")
            fecha_iso = s["data"].get("fecha_entrevista")

            if confirmed:
                try:
                    fecha_obj = datetime.fromisoformat(fecha_iso)
                    fecha_fmt = fecha_obj.strftime("%d/%m a las %H:%M")
                except:
                    fecha_fmt = "la fecha indicada"

                final_msg = (
                    f"? ¡Excelente! Tu entrevista ha sido agendada para el *{fecha_fmt}*.\n"
                    "Te esperamos en: *Av. Prol. Huaylas 1720, Chorrillos*.\n"
                    "No olvides llevar tu DNI y CV impreso. ¡Éxitos! ??"
                )
            else:
                final_msg = (
                    "Entendido. Lamentamos que no puedas asistir en este horario. ??\n"
                    "Dejaremos tus datos registrados y te contactaremos si se abre otra fecha. ¡Gracias!"
                )
        else:
            razones_txt = ", ".join(razones) if razones else "perfil no ajustado"
            # Mensaje suave de rechazo
            final_msg = (
                "Muchas gracias por completar tu postulación. ??\n"
                "Hemos registrado correctamente tu información.\n"
                "Tu perfil será evaluado y considerado en los procesos correspondientes.\n"
                "¡Gracias por tu interés en Hermes Transportes Blindados!"
                     )


        s["final_response"] = final_msg
        self._add_to_history(chat_id, "assistant", final_msg)
        return final_msg

    # -------------------------------------------------------------
    # Validación heurística
    # -------------------------------------------------------------
    def _validate_and_extract_soft(self, key: str, text: str, current: Dict[str, Any]) -> tuple[bool, Dict[str, Any], Optional[str]]:
        t = text.strip()
        tn = _norm_text(text)
        out: Dict[str, Any] = {}

        if key == "autorizacion_datos":
            y = self._yes_no_soft(tn)
            if y is True:
                out["autorizacion_datos"] = True
                return True, out, None
            if y is False:
                # Si dice NO, terminamos la sesión (o manejamos rechazo)
                # Por ahora retornamos False con mensaje de despedida/error
                return False, {}, "Entendido. Sin tu consentimiento no podemos continuar con el proceso. Gracias por tu interés. ??"

            return False, {}, "Por favor responde *Sí* o *Acepto* para continuar, o *No* para salir."

        if key == "nombre":
            if len(t.split()) >= 1:
                out["nombres"] = t
                return True, out, None
            return False, {}, "Por favor ingresa tus nombres."

        if key == "apellidos":
            if len(t.split()) >= 1:
                out["apellidos"] = t
                nombres = current.get("nombres", "")
                out["nombre_completo"] = f"{nombres} {t}".strip()
                return True, out, None
            return False, {}, "Por favor ingresa tus apellidos."

        if key == "edad":
            age = _extract_int(t)
            if age is not None:
                # Regla de Negocio (Filtro oculto)
                # Si es menor de 18 o mayor de 50, pedimos verificar (Generic Retry)
                if age < 18 or age > 50:
                    return False, {}, "Por favor, verifica tu respuesta e ingresa tu edad correcta en números."

                # Si pasa el filtro, guardamos
                out["edad"] = age
                return True, out, None

            return False, {}, "Ingresa una edad válida (número)."

        if key == "genero":
            if "masculino" in tn or "hombre" in tn or tn == "m":
                out["genero"] = "M"
                return True, out, None
            if "femenino" in tn or "mujer" in tn or tn == "f":
                out["genero"] = "F"
                return True, out, None
            if "otro" in tn or "prefiero" in tn:
                out["genero"] = "O"
                return True, out, None
            return False, {}, "Elige: Masculino, Femenino u Otros."

        if key == "tipo_documento":
            # 1. Inferencia por números: Si pone 8 dígitos, es DNI.
            nums_only = re.sub(r"\D", "", t)
            if len(nums_only) == 8:
                out["tipo_documento"] = "dni"
                out["dni"] = True
                out["numero_documento"] = nums_only  # Autocorregir step siguiente
                return True, out, None

            if "dni" in tn:
                out["tipo_documento"] = "dni"
                out["dni"] = True # Legacy
                return True, out, None
            if "extranjeria" in tn or "ce" in tn or "c.e" in tn:
                out["tipo_documento"] = "ce"
                out["dni"] = False # Legacy
                return True, out, None
            return False, {}, "Responde DNI o Carné de Extranjería."

        if key == "numero_documento":
            # 1. Limpieza agresiva pero smart
            nums = re.sub(r"\D", "", t)
            tipo = current.get("tipo_documento")

            # Caso CE
            if tipo == "ce":
                if len(nums) >= 8:
                    out["numero_documento"] = nums
                    return True, out, None
                return False, {}, "El Carné de Extranjería debe tener al menos 8 dígitos."

            # Caso DNI (o default) -> REGLA ESTRICTA 8 DÍGITOS
            if len(nums) == 8:
                out["numero_documento"] = nums
                if not tipo:
                    out["tipo_documento"] = "dni"
                    out["dni"] = True
                return True, out, None

            # Si tiene 9 o más, es error (probablemente tipeó mal o puso otro número)
            if len(nums) > 8:
                return False, {}, f"Parece que escribiste {len(nums)} números. El DNI debe tener exactamente 8."

            # Si tiene menos de 8
            if len(nums) < 8 and len(nums) > 0:
                return False, {}, f"Solo detecté {len(nums)} números. El DNI debe tener 8."

            return False, {}, "Por favor escribe solo el número de tu DNI."

        if key == "telefono":
            nums = re.sub(r"\D", "", t)
            # REGLA ESTRICTA 9 DÍGITOS (Celular Perú)
            if len(nums) == 9:
                out["telefono_contacto"] = nums
                return True, out, None

            if len(nums) > 9:
                return False, {}, f"Detecté {len(nums)} dígitos. El celular debe tener exactamente 9."

            return False, {}, "El teléfono debe tener exactamente 9 dígitos."

        if key == "correo":
            if re.match(r"[^@]+@[^@]+\.[^@]+", t):
                out["correo_electronico"] = t
                return True, out, None
            return False, {}, "El correo electrónico no es válido (ej. usuario@dominio.com)."

        if key == "secundaria":
            higher_ed = ["universidad", "universitario", "tecnico", "instituto", "maestria", "doctorado", "bachiller", "titulado", "egresado", "superior"]
            if any(w in tn for w in higher_ed):
                out["secundaria"] = True
                return True, out, None

            if "completa" in tn or "si" in tn or "culminad" in tn:
                out["secundaria"] = True
                return True, out, None
            if "incompleta" in tn or "no" in tn or "trunca" in tn:
                out["secundaria"] = False
                return True, out, None
            return False, {}, "¿Secundaria Completa? (Sí / No)"

        if key == "trabajo_hermes":
            # Eliminamos keywords hardcodeadas para dejar que la IA interprete
            y = self._yes_no_soft(tn)
            if y is not None:
                out["ha_trabajado_en_hermes"] = y
                return True, out, None
            return False, {}, "¿Has trabajado en Hermes? (Sí / No)"

        if key == "modalidad":
            if "1" in t: out["modalidad_trabajo"] = "tiempo_completo"; return True, out, None
            if "2" in t: out["modalidad_trabajo"] = "medio_tiempo"; return True, out, None
            if "3" in t: out["modalidad_trabajo"] = "intermitente"; return True, out, None
            if "tiempo completo" in tn or "full" in tn: out["modalidad_trabajo"] = "tiempo_completo"; return True, out, None
            if "medio" in tn or "part" in tn: out["modalidad_trabajo"] = "medio_tiempo"; return True, out, None
            if "intermitente" in tn or "dias" in tn: out["modalidad_trabajo"] = "intermitente"; return True, out, None
            return False, {}, "Elige una opción válida (1, 2 o 3)."

        if key == "distrito":
            out["distrito_residencia"] = t
            return True, out, None

        if key == "lugar_residencia":
            loc = _detect_location(t)
            if loc == "lima":
                out["lugar_residencia"] = "Lima"
                out["origen"] = "lima"
                out["ciudad_residencia"] = "Lima"
                return True, out, None
            if loc == "provincia":
                out["lugar_residencia"] = "Provincia"
                out["origen"] = "provincia"
                return True, out, None

            lima_districts = ["surco", "miraflores", "san isidro", "borja", "molina", "chorrillos", "barranco", "lince", "jesus maria", "magdalena", "pueblo libre", "san miguel", "callao", "olivos", "comas", "sj", "villa", "ate", "santa anita", "rimac", "breña", "victoria", "agustino", "independencia", "puente piedra", "carabayllo", "lurigancho", "chaclacayo", "cieneguilla", "lurin", "pachacamac", "pucusana", "punta hermosa", "punta negra", "san bartolo", "santa maria", "ancon", "santa rosa"]
            if any(d in tn for d in lima_districts):
                out["lugar_residencia"] = "Lima"
                out["origen"] = "lima"
                out["ciudad_residencia"] = "Lima"
                return True, out, None

            return False, {}, "¿Lima o Provincia?"

        if key == "ciudad":
            out["ciudad_residencia"] = t
            return True, out, None

        if key == "licencia":
            y = self._yes_no_soft(tn)
            if y is not None:
                out["licencia"] = y
                return True, out, None
            return False, {}, "¿Tienes licencia? (Sí / No)"

        if key == "licencia_tipo":
            cat = _detect_licencia_categoria(t)
            if cat:
                out["licencia_cat"] = cat
                return True, out, None
            return False, {}, "Indica la categoría (A1, A2B, etc.) o escribe 'No sé'."

        if key == "puesto":
            num_match = re.search(r"\b(\d{1,2})\b", t)
            if num_match:
                try:
                    num = int(num_match.group(1))
                    if 1 <= num <= len(PUESTOS):
                        p = next(x for x in PUESTOS if x["id"] == num)
                        out["puesto_id"] = p["id"]
                        out["puesto_name"] = p["name"]
                        # Auto-fill destino based on puesto
                        puesto_loc = PUESTO_UBICACION.get(p["id"], "Ambos")
                        out["destino"] = puesto_loc.lower() if puesto_loc != "Ambos" else "ambos"
                        return True, out, None
                except: pass

            info = _puesto_from_text(t)
            if info:
                out.update(info)
                # Auto-fill destino
                if "puesto_id" in out:
                    pid = out["puesto_id"]
                    puesto_loc = PUESTO_UBICACION.get(pid, "Ambos")
                    out["destino"] = puesto_loc.lower() if puesto_loc != "Ambos" else "ambos"
                return True, out, None
            return False, {}, "Elige una opción del menú (número)."

        if key == "disponibilidad":
            y = self._yes_no_soft(tn)
            if y is not None:
                out["disponibilidad"] = y
                return True, out, None
            return False, {}, "¿Disponibilidad inmediata? (Sí / No)"

        if key == "medio_captacion":
            mapping = {
                "1": "tiktok", "2": "canal_whatsapp", "3": "correo",
                "4": "volante", "5": "qr", "6": "facebook",
                "7": "referido", "8": "instagram", "9": "otros"
            }
            m = re.search(r"\b([1-9])\b", t)
            if m and m.group(1) in mapping:
                out["medio_captacion"] = mapping[m.group(1)]
                return True, out, None

            if "tiktok" in tn: out["medio_captacion"] = "tiktok"; return True, out, None
            if "whatsapp" in tn: out["medio_captacion"] = "canal_whatsapp"; return True, out, None
            if "correo" in tn or "email" in tn: out["medio_captacion"] = "correo"; return True, out, None
            if "volante" in tn: out["medio_captacion"] = "volante"; return True, out, None
            if "qr" in tn: out["medio_captacion"] = "qr"; return True, out, None
            if "facebook" in tn: out["medio_captacion"] = "facebook"; return True, out, None
            if "referido" in tn: out["medio_captacion"] = "referido"; return True, out, None
            if "instagram" in tn: out["medio_captacion"] = "instagram"; return True, out, None
            if "otro" in tn: out["medio_captacion"] = "otros"; return True, out, None

            return False, {}, "Elige una opción válida (1-9)."

        if key == "medio_captacion_otro":
            out["medio_captacion_otro"] = t
            return True, out, None

        if key == "confirmacion_entrevista":
            y = self._yes_no_soft(tn)

            # Recuperar fecha propuesta o calcular de nuevo si no está (edge case)
            fecha_iso = current.get("propuesta_fecha")
            if not fecha_iso:
                fecha_iso, _, _ = self._get_next_valid_slot()

            out["fecha_entrevista"] = fecha_iso

            if y is True:
                out["confirmacion_asistencia"] = True
                return True, out, None
            if y is False:
                out["confirmacion_asistencia"] = False
                return True, out, None

            return False, {}, "Por favor confirma si puedes asistir (Sí / No)."

        if key == "puesto_otros":
            out["puesto_otros_detalle"] = t
            return True, out, None

        if key == "puesto_mineria_sucursal":
            # 1. Arequipa, 2. Trujillo, 3. Huanuco, 4. Cusco, 5. Otros
            mapping = {
                "1": "Arequipa", "2": "Trujillo", "3": "Huanuco", "4": "Cusco", "5": "Otros"
            }
            # Match por numero
            m = re.search(r"\b([1-5])\b", t)
            if m:
                out["puesto_otros_detalle"] = mapping[m.group(1)] # Reutilizamos campo
                return True, out, None

            # Match por texto
            tn_lower = tn.lower()
            if "arequipa" in tn_lower: out["puesto_otros_detalle"] = "Arequipa"; return True, out, None
            if "trujillo" in tn_lower: out["puesto_otros_detalle"] = "Trujillo"; return True, out, None
            if "huanuco" in tn_lower: out["puesto_otros_detalle"] = "Huanuco"; return True, out, None
            if "cusco" in tn_lower: out["puesto_otros_detalle"] = "Cusco"; return True, out, None
            if "otro" in tn_lower: out["puesto_otros_detalle"] = "Otros"; return True, out, None

            return False, {}, "Elige una opción válida (1-5)."

        return False, {}, "No entendí tu respuesta."

    def _yes_no_soft(self, tn: str) -> Optional[bool]:
        yes_markers = {"si", "sí", "sip", "claro", "yes", "correcto", "obvio", "acepto", "simon", "dale", "por supuesto"}
        no_markers = {"no", "nop", "negativo", "nunca", "jamas", "nel", "naranjas"}

        # Tokenización simple para evitar falsos positivos parciales, pero permitiendo frases
        # "simon" -> True, "nel" -> False

        # 1. Match exacto o palabra única
        if tn in yes_markers: return True
        if tn in no_markers: return False

        # 2. Búsqueda en texto
        for m in yes_markers:
            # \b para palabras completas
            if re.search(rf"\b{re.escape(m)}\b", tn): return True

        for m in no_markers:
            if re.search(rf"\b{re.escape(m)}\b", tn): return False

        return None

        return None

    # -------------------------------------------------------------
    # Reglas de Aptitud (Evaluación final)
    # -------------------------------------------------------------
    def _evaluate_aptitud(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        reasons = []
        # 1. Edad
        edad = data.get("edad")
        if isinstance(edad, int):
            if edad < 18 or edad > 50:
                reasons.append("Edad fuera de rango (18-50)")

        # 2. Ubicación (Regla Puesto vs Origen ESTRICTA)
        puesto_id = data.get("puesto_id")
        origen = data.get("origen") # "lima" o "provincia"

        if puesto_id:
            puesto_loc = PUESTO_UBICACION.get(puesto_id, "Ambos")

            if puesto_loc == "Lima" and origen != "lima":
                reasons.append("Postulante de Provincia para puesto en Lima")
            elif puesto_loc == "Provincia" and origen != "provincia":
                 reasons.append("Postulante de Lima para puesto en Provincia")

        # 2b. Regla Especial Minería (Puestos 12 y 13)
        if puesto_id in [12, 13]:
            # El usuario eligió una Sucursal (guardada en puesto_otros_detalle)
            # Y declaró una provincia en 'ciudad_residencia' (Q14)
            sucursal = data.get("puesto_otros_detalle") # "Trujillo", "Arequipa", etc.
            ciudad_residencia = data.get("ciudad_residencia", "")

            if not sucursal or not ciudad_residencia:
                reasons.append("Faltan datos de ubicación Minería")
            else:
                # Validar Match: Ciudad vs Sucursal
                match_ok = False

                # Check 1: Match directo de texto
                s_norm = _norm_text(sucursal)
                c_norm = _norm_text(ciudad_residencia)

                if s_norm in c_norm or c_norm in s_norm:
                    match_ok = True

                # Check 2: Sinonimos conocidos (La Libertad -> Trujillo)
                # Expandir según necesidad
                if not match_ok:
                    if "libertad" in c_norm and "trujillo" in s_norm: match_ok = True

                # Check 3: Gemini (Fuzzy semantic match)
                if not match_ok and self.gemini:
                    try:
                        # Preguntamos a Gemini si la ciudad X pertenece a la región Y
                        ctx_val = (
                            f"El candidato dice vivir en: '{ciudad_residencia}'.\n"
                            f"La sucursal/región requerida es: '{sucursal}'.\n"
                            "Responde SOLO 'SI' si la ciudad está en esa región o es la misma, o 'NO' si es diferente."
                        )
                        val_resp = self.gemini.respuesta_conversacional("", ctx_val, {})
                        if val_resp and "si" in _norm_text(val_resp):
                             match_ok = True
                    except: pass

                if not match_ok and sucursal != "Otros":
                   # Si es 'Otros', quizás somos laxos o lo mandamos a revisión.
                   # Asumiremos que si eligió 'Otros', requiere validación manual, pero no auto-rechazo
                   # O según regla: "solo para esos caso... regla de aptos y no aptos varía"
                   # Si puso Sucursal=Arequipa y vive en Iquitos -> No Apto.
                   reasons.append(f"Ubicación ({ciudad_residencia}) no coincide con Sucursal ({sucursal})")

        # 3. Secundaria
        if not data.get("secundaria"):
            reasons.append("Sin secundaria completa")

        # 4. Documento (CE descartado)
        if data.get("tipo_documento") == "ce":
             reasons.append("Carné de Extranjería no aceptado")

        # 5. Licencia para puestos 8 y 9
        if puesto_id in [8, 9] and not data.get("licencia"):
            reasons.append("Puesto requiere licencia")

        # 6. Disponibilidad
        if not data.get("disponibilidad"):
            reasons.append("Sin disponibilidad inmediata")

        return len(reasons) == 0, reasons

    # -------------------------------------------------------------
    # Lógica de Aforo / Fechas Validás
    # -------------------------------------------------------------
    def _get_next_valid_slot(self) -> tuple[str, str, str]:
        """
        Busca el siguiente día hábil (Lun-Vie) con aforo disponible (<40).
        Retorna (iso_full_datetime, dia_semana_esp, fecha_corta_dd_mm).
        """
        candidate = datetime.now() + timedelta(days=1)

        # Límite de búsqueda para evitar loop infinito (ej. 30 días)
        for _ in range(30):
            # 1. Ajuste Fin de Semana (Lunes a Viernes solamente)
            wd = candidate.weekday() # 0=Mon ... 6=Sun
            if wd == 5: # Sábado -> Lunes
                candidate += timedelta(days=2)
            elif wd == 6: # Domingo -> Lunes
                candidate += timedelta(days=1)

            # Ahora candidate es Mon-Fri

            # 2. Check Capacity en DB
            # Formato ISO base para la query
            iso_check = candidate.strftime("%Y-%m-%d")

            count = 0
            if self.db and hasattr(self.db, "get_count_for_date"):
                count = self.db.get_count_for_date(iso_check)

            if count < 40:
                # Slot encontrado!
                candidate = candidate.replace(hour=8, minute=30, second=0, microsecond=0)

                # Formatear
                dia_str = candidate.strftime("%A")
                dias = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", "Thursday": "Jueves", "Friday": "Viernes"}
                dia_esp = dias.get(dia_str, dia_str)
                fecha_fmt_short = candidate.strftime("%d/%m")

                return candidate.isoformat(), dia_esp, fecha_fmt_short

            else:
                # Día lleno, probar siguiente
                candidate += timedelta(days=1)

        # Fallback (si todo lleno por 1 mes, devolvemos mañana igual para no romper, o log error)
        fallback = datetime.now() + timedelta(days=1)
        return fallback.isoformat(), "mañana", fallback.strftime("%d/%m")

    def _forced_options_question(self, key: str) -> str:
        return f"Por favor responde la pregunta ({key}) de forma clara."
