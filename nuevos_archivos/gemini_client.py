import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

class GeminiClient:
    """
    Cliente mejorado para Gemini con múltiples funciones contextuales.
    """
    
    def __init__(self):
        self.model = genai.GenerativeModel(MODEL)
    
    def _generate(self, prompt: str, max_retries: int = 2) -> str:
        """Método base para generar contenido con reintentos"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                if response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[Gemini Error - Intento {attempt + 1}] {e}")
                if attempt == max_retries - 1:
                    return None
        return None

    def answer_company_question(self, question: str, company_info: dict) -> str:
        """
        Responde preguntas sobre la empresa de forma concisa y profesional.
        """
        prompt = f"""Eres un asistente de RRHH de {company_info['nombre']}.

INFORMACIÓN DE LA EMPRESA:
- Nombre: {company_info['nombre']}
- Descripción: {company_info['descripcion']}
- Valores: {company_info['valores']}

PREGUNTA DEL CANDIDATO: {question}

INSTRUCCIONES:
- Responde de forma breve (máximo 3-4 líneas)
- Sé profesional pero amigable
- Si no sabes la respuesta exacta, da información general positiva
- Finaliza invitando a comenzar la postulación

RESPUESTA:"""

        response = self._generate(prompt)
        
        if response:
            return response
        else:
            return (
                f"{company_info['nombre']} es una {company_info['descripcion']}. "
                "¿Te gustaría comenzar tu postulación? Escribe *empezar*."
            )

    def help_with_answer(self, question: str, user_response: str, hint: str) -> str:
        """
        Ayuda al usuario a entender qué tipo de respuesta se espera.
        """
        prompt = f"""Eres un asistente amable de RRHH que está ayudando a un candidato a responder correctamente.

PREGUNTA QUE DEBE RESPONDER: {question}
RESPUESTA DEL CANDIDATO: {user_response}
HINT: Debe indicar {hint}

CONTEXTO: El candidato no está respondiendo la pregunta de forma clara.

INSTRUCCIONES:
- Sé muy breve (máximo 2 líneas)
- Explica amablemente qué tipo de respuesta necesitas
- Da un ejemplo si es necesario
- No repitas la pregunta completa, solo orienta

RESPUESTA:"""

        response = self._generate(prompt)
        
        if response:
            return f"{response}\n\n*Pregunta:* {question}"
        else:
            return (
                f"Por favor, necesito que respondas indicando {hint}.\n\n"
                f"*Pregunta:* {question}"
            )

    def handle_post_completion_question(self, question: str) -> str:
        """
        Maneja preguntas después de completar el cuestionario.
        """
        prompt = f"""Eres un asistente de RRHH. Un candidato ya completó su postulación y tiene esta consulta:

CONSULTA: {question}

INSTRUCCIONES:
- Responde de forma breve y útil (máximo 3 líneas)
- Si pregunta por tiempos: menciona que RRHH contactará en 48-72 horas
- Si pregunta por resultados: indica que debe esperar la llamada del equipo
- Si pregunta algo que no puedes responder: indica que RRHH le dará esa información
- Mantén un tono profesional y amable

RESPUESTA:"""

        response = self._generate(prompt)
        
        if response:
            return response
        else:
            return (
                "Nuestro equipo de Recursos Humanos revisará tu postulación "
                "y se comunicará contigo en las próximas 48-72 horas. "
                "Para consultas específicas, ellos te brindarán toda la información necesaria."
            )

    def short_response(self, user_input: str) -> str:
        """
        Método legacy para compatibilidad (respuesta genérica corta).
        """
        prompt = f"""Eres un asistente amable de RRHH. El candidato escribió: "{user_input}"

Responde de forma muy breve (1-2 líneas) y amable, guiándolo a responder correctamente.

RESPUESTA:"""

        response = self._generate(prompt)
        return response if response else "¿Podrías ser más específico/a en tu respuesta?"