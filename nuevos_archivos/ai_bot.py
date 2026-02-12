import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from .gemini_client import GeminiClient

load_dotenv()

SESSION_TIMEOUT_MINUTES = 60
COOLDOWN_HOURS = 24  # Tiempo de espera después de completar el cuestionario

class AIBot:
    """
    Bot IA para guiar postulantes a través de 8 preguntas de preselección.
    Utiliza Gemini para validar respuestas y mantener el contexto conversacional.
    """

    def __init__(self):
        self.sessions = {}
        self.gemini = GeminiClient()
        
        # Información de la empresa para contexto
        self.company_info = {
            "nombre": "Hermes Transportes Blindados",
            "descripcion": "Empresa líder en transporte de valores y seguridad",
            "valores": "Compromiso, seguridad, confiabilidad y profesionalismo"
        }
        
        # Preguntas estructuradas con validaciones
        self.questions = [
            {
                "id": 1,
                "text": "1/8) ¿A qué puesto postulas? (ej.: Conductor A2B, Motorizado, Operario, Vigilante...)",
                "key": "puesto",
                "validation_hint": "nombre del puesto"
            },
            {
                "id": 2,
                "text": "2/8) ¿Cuál es tu edad?",
                "key": "edad",
                "validation_hint": "tu edad en números"
            },
            {
                "id": 3,
                "text": "3/8) ¿En qué ciudad o provincia te encuentras?",
                "key": "ubicacion",
                "validation_hint": "la ciudad donde resides"
            },
            {
                "id": 4,
                "text": "4/8) ¿Tienes DNI o Carné de Extranjería vigente?",
                "key": "documento",
                "validation_hint": "si tienes DNI o carné de extranjería vigente (responde Sí o No)"
            },
            {
                "id": 5,
                "text": "5/8) ¿Cuál es tu nivel de estudios? (Primaria, Secundaria, Técnica, Universitaria...)",
                "key": "estudios",
                "validation_hint": "tu nivel de estudios"
            },
            {
                "id": 6,
                "text": "6/8) ¿Tienes experiencia previa en el puesto al que postulas? (Indica años o 'sin experiencia')",
                "key": "experiencia",
                "validation_hint": "tu experiencia laboral en el puesto"
            },
            {
                "id": 7,
                "text": "7/8) ¿Tienes licencia de conducir? ¿Qué categoría? (Si no tienes, indica 'No tengo')",
                "key": "licencia",
                "validation_hint": "si tienes licencia y qué categoría"
            },
            {
                "id": 8,
                "text": "8/8) ¿Tienes disponibilidad inmediata para comenzar a trabajar?",
                "key": "disponibilidad",
                "validation_hint": "si tienes disponibilidad inmediata (responde Sí o No)"
            }
        ]

    # -------------------------------
    # Helpers de Sesión
    # -------------------------------
    def _init_session(self, chat_id):
        """Inicializa una nueva sesión de usuario"""
        self.sessions[chat_id] = {
            "current_step": 0,
            "answers": {},
            "retry_count": 0,
            "last_activity": datetime.now(),
            "completed": False,
            "completion_time": None,
            "in_conversation": True
        }

    def _reset_session(self, chat_id):
        """Reinicia la sesión manteniendo el historial de completado"""
        old_completion = self.sessions.get(chat_id, {}).get("completion_time")
        self._init_session(chat_id)
        if old_completion:
            self.sessions[chat_id]["completion_time"] = old_completion

    def _is_session_expired(self, chat_id):
        """Verifica si la sesión ha expirado por inactividad"""
        session = self.sessions.get(chat_id)
        if not session:
            return True
        return datetime.now() - session["last_activity"] > timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    def _can_restart(self, chat_id):
        """Verifica si el usuario puede reiniciar el cuestionario (cooldown de 24h)"""
        session = self.sessions.get(chat_id)
        if not session or not session.get("completion_time"):
            return True
        
        time_since_completion = datetime.now() - session["completion_time"]
        return time_since_completion > timedelta(hours=COOLDOWN_HOURS)

    def _update_activity(self, chat_id):
        """Actualiza el timestamp de última actividad"""
        if chat_id in self.sessions:
            self.sessions[chat_id]["last_activity"] = datetime.now()

    # -------------------------------
    # Validaciones de Respuesta
    # -------------------------------
    def _is_valid_response(self, text, question_key):
        """
        Validación básica de respuestas según el tipo de pregunta
        """
        text = text.strip().lower()
        
        # Respuestas claramente inválidas
        invalid_responses = [
            "", "no se", "nose", "no sé", "?", "??", "???",
            "hola", "buenas", "buenos dias", "buenas tardes",
            "empezar", "iniciar", "comenzar"
        ]
        
        if text in invalid_responses or len(text) < 2:
            return False
        
        # Validaciones específicas por tipo de pregunta
        if question_key == "edad":
            # Debe contener al menos un número
            return any(char.isdigit() for char in text)
        
        elif question_key in ["documento", "disponibilidad"]:
            # Debe ser una respuesta afirmativa/negativa clara
            positive = ["si", "sí", "yes", "tengo", "claro", "correcto", "afirmativo"]
            negative = ["no", "nop", "negativo", "no tengo"]
            return any(word in text for word in positive + negative)
        
        return True

    # -------------------------------
    # Manejo de Información de Empresa
    # -------------------------------
    def _handle_company_question(self, text):
        """Responde preguntas sobre la empresa usando Gemini"""
        try:
            response = self.gemini.answer_company_question(text, self.company_info)
            return response
        except Exception as e:
            print(f"[ERROR] Error al responder pregunta de empresa: {e}")
            return (
                f"Somos *{self.company_info['nombre']}*, {self.company_info['descripcion']}. "
                "¿Te gustaría comenzar con tu postulación? Escribe *empezar* cuando estés listo/a."
            )

    # -------------------------------
    # Generación de Resumen
    # -------------------------------
    def _generate_summary(self, session):
        """Genera un resumen estructurado de las respuestas"""
        answers = session["answers"]
        lines = ["📋 *RESUMEN DE TU POSTULACIÓN*\n"]
        
        for q in self.questions:
            answer = answers.get(q["key"], "No respondido")
            question_text = q["text"].split(') ')[1].split('?')[0]
            lines.append(f"▫️ {question_text}: *{answer}*")
        
        return "\n".join(lines)

    # -------------------------------
    # Método Principal de Procesamiento
    # -------------------------------
    def process(self, chat_id, text):
        """
        Método principal para procesar mensajes del usuario.
        Maneja todo el flujo conversacional del bot.
        """
        if not text or not text.strip():
            return "Por favor, envía un mensaje de texto para continuar."
        
        text_original = text.strip()
        text_lower = text_original.lower()

        # ===== 1. COMANDOS GLOBALES =====
        
        # Comando de ayuda
        if text_lower in ["ayuda", "help", "menu", "opciones"]:
            return (
                "🤖 *Comandos disponibles:*\n\n"
                "▫️ *empezar* - Iniciar postulación\n"
                "▫️ *reiniciar* - Reiniciar proceso\n"
                "▫️ *estado* - Ver tu progreso\n"
                "▫️ *ayuda* - Ver este menú\n\n"
                "También puedes hacerme preguntas sobre la empresa."
            )

        # ===== 2. VERIFICAR O CREAR SESIÓN =====
        
        # Si no existe sesión o expiró
        if chat_id not in self.sessions or self._is_session_expired(chat_id):
            
            # Saludos y preguntas sobre la empresa antes de empezar
            if any(word in text_lower for word in ["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches"]):
                self._init_session(chat_id)
                self.sessions[chat_id]["in_conversation"] = True
                return (
                    f"¡Hola! 👋 Bienvenido/a a *{self.company_info['nombre']}*.\n\n"
                    "Soy tu asistente virtual de Recursos Humanos. Estoy aquí para ayudarte con tu postulación.\n\n"
                    "Puedes preguntarme sobre la empresa o escribir *empezar* para iniciar tu registro."
                )
            
            # Preguntas sobre la empresa
            elif any(word in text_lower for word in ["empresa", "hermes", "trabajan", "hacen", "dedicamos", "informacion"]):
                self._init_session(chat_id)
                self.sessions[chat_id]["in_conversation"] = True
                response = self._handle_company_question(text_original)
                return f"{response}\n\nCuando estés listo/a para postular, escribe *empezar*."
            
            # Iniciar proceso
            elif any(word in text_lower for word in ["empezar", "iniciar", "comenzar", "postular", "registrar"]):
                self._init_session(chat_id)
                return (
                    f"¡Perfecto! 🎯\n\n"
                    f"Te haré *8 preguntas rápidas* para conocer tu perfil.\n"
                    f"El proceso toma solo 2-3 minutos.\n\n"
                    f"Empecemos:\n\n{self.questions[0]['text']}"
                )
            
            # Primera interacción sin saludo
            else:
                self._init_session(chat_id)
                self.sessions[chat_id]["in_conversation"] = True
                return (
                    f"Hola 👋 Soy el asistente de *{self.company_info['nombre']}*.\n\n"
                    "Puedes preguntarme sobre la empresa o escribir *empezar* para iniciar tu postulación."
                )

        # ===== 3. SESIÓN ACTIVA =====
        
        session = self.sessions[chat_id]
        self._update_activity(chat_id)

        # ===== 4. VERIFICAR SI YA COMPLETÓ EL CUESTIONARIO =====
        
        if session["completed"]:
            
            # Comando de estado
            if text_lower == "estado":
                return (
                    "✅ Ya completaste tu postulación.\n\n"
                    "Nuestro equipo de RRHH revisará tu información y se comunicará contigo pronto.\n\n"
                    "Si tienes alguna consulta, puedo intentar ayudarte."
                )
            
            # Intento de reiniciar
            if text_lower in ["reiniciar", "empezar", "iniciar", "comenzar"]:
                if self._can_restart(chat_id):
                    self._reset_session(chat_id)
                    return (
                        "🔄 De acuerdo, reiniciaremos el proceso.\n\n"
                        f"{self.questions[0]['text']}"
                    )
                else:
                    completion_time = session["completion_time"]
                    hours_passed = (datetime.now() - completion_time).total_seconds() / 3600
                    hours_remaining = COOLDOWN_HOURS - int(hours_passed)
                    
                    return (
                        "⏳ Ya completaste tu postulación recientemente.\n\n"
                        f"Podrás volver a postular en aproximadamente *{hours_remaining} horas*.\n\n"
                        "Si tienes alguna duda, puedo ayudarte con información general."
                    )
            
            # Preguntas post-completado
            else:
                response = self.gemini.handle_post_completion_question(text_original)
                return response

        # ===== 5. EN PROCESO DE RESPONDER PREGUNTAS =====
        
        current_step = session["current_step"]
        current_question = self.questions[current_step]
        
        # Comando de estado durante el proceso
        if text_lower == "estado":
            return (
                f"📊 *Progreso: {current_step}/{len(self.questions)}*\n\n"
                f"Pregunta actual:\n{current_question['text']}"
            )
        
        # Comando de reiniciar durante el proceso
        if text_lower in ["reiniciar", "empezar de nuevo", "volver a empezar"]:
            self._reset_session(chat_id)
            return (
                "🔄 Proceso reiniciado.\n\n"
                f"{self.questions[0]['text']}"
            )
        
        # ===== 6. PROCESAR RESPUESTA A LA PREGUNTA ACTUAL =====
        
        question_key = current_question["key"]
        
        # Validar respuesta
        if not self._is_valid_response(text_original, question_key):
            session["retry_count"] += 1
            
            # Después de 3 intentos fallidos, usar Gemini para ayudar
            if session["retry_count"] >= 3:
                hint = self.gemini.help_with_answer(
                    question=current_question["text"],
                    user_response=text_original,
                    hint=current_question["validation_hint"]
                )
                session["retry_count"] = 0
                return hint
            
            return (
                f"🤔 Necesito que respondas la pregunta para continuar.\n\n"
                f"*Pregunta:* {current_question['text']}\n\n"
                f"Por favor, indica {current_question['validation_hint']}."
            )
        
        # Respuesta válida - guardar y avanzar
        session["answers"][question_key] = text_original
        session["retry_count"] = 0
        current_step += 1
        session["current_step"] = current_step
        
        # ===== 7. VERIFICAR SI COMPLETÓ TODAS LAS PREGUNTAS =====
        
        if current_step >= len(self.questions):
            session["completed"] = True
            session["completion_time"] = datetime.now()
            
            summary = self._generate_summary(session)
            
            return (
                f"{summary}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✅ *Estado: PRE-APTO*\n\n"
                "¡Gracias por completar tu postulación! 🎉\n\n"
                "Nuestro equipo de Recursos Humanos revisará tu información "
                "y se pondrá en contacto contigo en las próximas 48-72 horas.\n\n"
                "¿Tienes alguna consulta adicional?"
            )
        
        # ===== 8. CONTINUAR CON LA SIGUIENTE PREGUNTA =====
        
        return f"✅ Perfecto.\n\n{self.questions[current_step]['text']}"