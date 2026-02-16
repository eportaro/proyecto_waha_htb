# test_bot_flow.py
import sys
import os

# Add the current directory to sys.path to make imports work
sys.path.append(os.getcwd())

from bot.ai_bot import AIBot

def run_test():
    print("🤖 Iniciando prueba de flujo del Bot...")
    bot = AIBot()
    chat_id = "test_user_123"
    
    # 1. Iniciar
    print(f"User: empezar")
    resp = bot.process(chat_id, "empezar")
    print(f"Bot: {resp}\n")
    
    # 2. Elegir puesto (ej. 8 - Conductor)
    print(f"User: 8")
    resp = bot.process(chat_id, "8")
    print(f"Bot: {resp}\n")
    
    # 3. Nombre
    print(f"User: Juan Perez")
    resp = bot.process(chat_id, "Juan Perez")
    print(f"Bot: {resp}\n")
    
    # 4. Edad (Apto: 25)
    print(f"User: 25")
    resp = bot.process(chat_id, "25")
    print(f"Bot: {resp}\n")
    
    # 5. Genero
    print(f"User: Masculino")
    resp = bot.process(chat_id, "Masculino")
    print(f"Bot: {resp}\n")
    
    # 6. Tipo Doc
    print(f"User: DNI")
    resp = bot.process(chat_id, "DNI")
    print(f"Bot: {resp}\n")
    
    # 7. Num Doc
    print(f"User: 12345678")
    resp = bot.process(chat_id, "12345678")
    print(f"Bot: {resp}\n")
    
    # 8. Telefono
    print(f"User: 999888777")
    resp = bot.process(chat_id, "999888777")
    print(f"Bot: {resp}\n")
    
    # 9. Correo
    print(f"User: juan@test.com")
    resp = bot.process(chat_id, "juan@test.com")
    print(f"Bot: {resp}\n")
    
    # 10. Secundaria
    print(f"User: Si")
    resp = bot.process(chat_id, "Si")
    print(f"Bot: {resp}\n")
    
    # 11. Trabajo Hermes
    print(f"User: No")
    resp = bot.process(chat_id, "No")
    print(f"Bot: {resp}\n")
    
    # 12. Modalidad
    print(f"User: Tiempo Completo")
    resp = bot.process(chat_id, "Tiempo Completo")
    print(f"Bot: {resp}\n")
    
    # 13. Distrito
    print(f"User: Chorrillos")
    resp = bot.process(chat_id, "Chorrillos")
    print(f"Bot: {resp}\n")
    
    # 14. Lugar Residencia (Lima) -> Debería saltar Ciudad
    print(f"User: Lima")
    resp = bot.process(chat_id, "Lima")
    print(f"Bot: {resp}\n")
    
    # 15. Licencia (Puesto 8 requiere licencia)
    print(f"User: Si")
    resp = bot.process(chat_id, "Si")
    print(f"Bot: {resp}\n")
    
    # 16. Tipo Licencia
    print(f"User: A1")
    resp = bot.process(chat_id, "A1")
    print(f"Bot: {resp}\n")
    
    # 17. Puesto (Ya elegido al inicio, pero el flujo pregunta de nuevo? 
    # Ah, el flujo original tenía 'puesto' como paso 1.
    # En mi nuevo flujo, 'puesto' está en el paso 16 (index 15).
    # Pero al inicio (step 0 -> 1) ya preguntamos puesto si detectamos start_intent?
    # Revisemos la lógica:
    # Si start_intent -> step=1. Step 1 es 'nombre'.
    # Espera, en el código `_init_session` pone step=0.
    # Si `start_intent` es True, pone step=1 y devuelve `_ask_next`.
    # `_ask_next` con step=1 (index 0) es 'nombre'.
    # ENTONCES EL PUESTO SE PREGUNTA EN EL PASO 16.
    # EL MENÚ INICIAL ES SOLO VISUAL O PARA INICIAR?
    # El código original usaba el menú para setear puesto en step 1.
    # Mi nuevo código tiene 'puesto' en la lista en la posición 16.
    # AJUSTE: El usuario quiere que replique el formulario. El formulario pregunta puesto casi al final (pregunta 17).
    # Entonces el menú inicial es solo "para empezar".
    # Vamos a seguir el flujo.)
    
    # ... Continuamos desde Licencia Tipo ...
    # El bot debería preguntar Puesto ahora.
    
    print(f"User: 8") # Respondiendo al Puesto
    resp = bot.process(chat_id, "8")
    print(f"Bot: {resp}\n")
    
    # 18. Disponibilidad
    print(f"User: Si")
    resp = bot.process(chat_id, "Si")
    print(f"Bot: {resp}\n")
    
    # 19. Medio Captacion
    print(f"User: Facebook")
    resp = bot.process(chat_id, "Facebook")
    print(f"Bot: {resp}\n")
    
    # 20. Horario Entrevista (Si es APTO)
    # Debería ser apto.
    print(f"User: 1") # Mañana
    resp = bot.process(chat_id, "1")
    print(f"Bot: {resp}\n")

    print("✅ Prueba finalizada.")
    
    # Verificar datos
    print("\nDatos capturados:")
    print(bot.sessions[chat_id]["data"])

if __name__ == "__main__":
    run_test()
