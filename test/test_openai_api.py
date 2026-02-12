import os
from dotenv import load_dotenv
from openai import OpenAI
import httpx

# Cargar .env
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ Falta OPENAI_API_KEY en el entorno.")
    exit(1)

# Cliente HTTP tolerante (desactiva verificación SSL si hay proxy interno)
http_client = httpx.Client(verify=False, timeout=30.0)
client = OpenAI(api_key=api_key, http_client=http_client)

print("💬 Prueba de chat interactivo con OpenAI")
print("Escribe 'salir' para terminar.\n")

while True:
    prompt = input("Tú: ").strip()
    if prompt.lower() in ["salir", "exit", "quit"]:
        print("👋 Fin del chat.")
        break

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional amigable y técnico."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        print("🤖 Bot:", response.choices[0].message.content.strip(), "\n")
    except Exception as e:
        print("❌ Error al conectar o generar respuesta:", e, "\n")
