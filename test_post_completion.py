import sys
import os
from datetime import datetime
from unittest.mock import MagicMock

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from bot.ai_bot import AIBot
from bot.gemini_client import GeminiClient

def test_post_completion():
    print("🤖 Iniciando prueba de post-completado...")
    
    # Mock GeminiClient to simulate the new JSON wrapping behavior
    mock_gemini = MagicMock()
    # Simulate valid JSON response from Gemini
    mock_gemini.extract_and_validate.return_value = {"is_valid": True, "extracted_data": {}}
    
    # Simulate conversational response (wrapped in JSON as per new prompt)
    # We need to test if AIBot correctly calls this and if GeminiClient (real logic) would unwrap it.
    # Since we are mocking Gemini, we can't test the unwrapping logic of GeminiClient here easily 
    # without instantiating a real GeminiClient.
    # But we can test AIBot's context construction.
    
    bot = AIBot(gemini=mock_gemini)
    chat_id = "test_user_completed"
    
    # Setup a completed session
    bot.sessions[chat_id] = {
        "step": 23, # Adjusted for new flow length
        "data": {
            "nombre_completo": "Juan Perez",
            "horario_entrevista": "10:30",
            "is_apto": True
        },
        "completed": True,
        "completion_time": datetime.now(),
        "is_apto": True,
        "last_activity": datetime.now(),
        "conversation_history": []
    }
    
    # Test conversational input
    print(f"User: Quiero cambiar mi horario")
    bot.process(chat_id, "Quiero cambiar mi horario")
    
    # Verify what AIBot sent to Gemini
    args, _ = mock_gemini.respuesta_conversacional.call_args
    user_msg, context, company_info = args
    
    print("\n--- Contexto enviado a Gemini ---")
    print(context)
    
    if "Estado: APTO" in context and "a las 10:30" in context: # Check for specific time format
        print("\n✅ Contexto construido correctamente.")
    elif "Estado: APTO" in context and "10:30" in context:
         print("\n✅ Contexto construido correctamente (con hora).")
    else:
        print("\n❌ Contexto incorrecto.")

if __name__ == "__main__":
    test_post_completion()
