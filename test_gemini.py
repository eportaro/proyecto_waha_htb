# test_gemini.py
import os
import sys
import argparse

try:
    from dotenv import load_dotenv
except Exception:
    print("ERROR: falta 'python-dotenv'. Instala con: pip install python-dotenv")
    sys.exit(1)

try:
    import google.generativeai as genai
except Exception:
    print("ERROR: falta 'google-generativeai'. Instala con: pip install google-generativeai")
    sys.exit(1)

def main():
    # Carga variables desde .env (en el cwd)
    load_dotenv()

    parser = argparse.ArgumentParser(description="Test simple de la API de Gemini.")
    parser.add_argument("--api-key", help="Override de GOOGLE_API_KEY")
    parser.add_argument("--model", help="Override de GEMINI_MODEL")
    parser.add_argument("--prompt", default="Di 'OK' si estás funcionando.", help="Prompt de prueba")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GOOGLE_API_KEY")
    model_name = args.model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        print("ERROR: falta GOOGLE_API_KEY (o --api-key).")
        sys.exit(1)

    # Configurar cliente
    genai.configure(api_key=api_key)

    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(args.prompt)
    except Exception as e:
        print(f"ERROR llamando al modelo '{model_name}': {e}")
        sys.exit(1)

    # Imprimir resultados
    print(f"✅ Model: {model_name}")
    try:
        text = getattr(resp, "text", None)
        if not text:
            # Fallback si no existe resp.text
            parts = []
            for cand in getattr(resp, "candidates", []) or []:
                for part in getattr(cand, "content", {}).get("parts", []):
                    parts.append(str(part))
            text = "\n".join(parts) if parts else "(sin texto)"
        print("—— Respuesta ——")
        print(text)
    except Exception as e:
        print(f"(No se pudo formatear la respuesta): {e}")

    # (Opcional) uso de tokens si está disponible
    usage = getattr(resp, "usage_metadata", None)
    if usage:
        try:
            print("—— Uso ——")
            print(usage)
        except:
            pass

if __name__ == "__main__":
    main()
