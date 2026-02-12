import sys
import os
sys.path.append(os.getcwd())
from bot.ai_bot import AIBot

def test_logic():
    bot = AIBot(db=None, gemini=None)
    
    print("\n--- Testing Data Consent ---")
    # Case 1: Yes
    valid, out, msg = bot._validate_and_extract_soft("autorizacion_datos", "sí, acepto", {})
    print(f"Consent 'Sí': {valid} (Expected True) - Val: {out.get('autorizacion_datos')}")
    
    # Case 2: No
    valid, out, msg = bot._validate_and_extract_soft("autorizacion_datos", "no acepto", {})
    print(f"Consent 'No': {valid} (Expected False) - Msg: {msg}")

    print("--- Testing DNI Validation ---")
    # Case 1: Valid DNI
    valid, out, msg = bot._validate_and_extract_soft("numero_documento", "12345678", {"tipo_documento": "dni"})
    print(f"DNI 8 digits: {valid} (Expected True)")
    
    # Case 2: Invalid DNI (7 digits)
    valid, out, msg = bot._validate_and_extract_soft("numero_documento", "1234567", {"tipo_documento": "dni"})

    print("\n--- Testing Phone Validation ---")
    # Case 1: Valid Phone
    valid, out, msg = bot._validate_and_extract_soft("telefono", "987654321", {})
    print(f"Phone 9 digits: {valid} (Expected True)")
    
    # Case 2: Invalid Phone (8 digits)
    valid, out, msg = bot._validate_and_extract_soft("telefono", "98765432", {})
    print(f"Phone 8 digits: {valid} (Expected False) - Msg: {msg}")

    print("\n--- Testing Age Validation ---")
    # Case 1: Valid Age (18-99)
    valid, out, msg = bot._validate_and_extract_soft("edad", "25", {})
    print(f"Age 25: {valid} (Expected True)")
    
    # Case 2: Valid Age (10-17) - Now allowed
    valid, out, msg = bot._validate_and_extract_soft("edad", "16", {})
    print(f"Age 16: {valid} (Expected True)")
    
    # Case 3: Invalid Age (<10)
    valid, out, msg = bot._validate_and_extract_soft("edad", "9", {})
    print(f"Age 9: {valid} (Expected False) - Msg: {msg}")

    print("\n--- Testing Hermes Work History (AI Fallback) ---")
    # Case 1: Simple Yes (Deterministic)
    valid, out, msg = bot._validate_and_extract_soft("trabajo_hermes", "sí", {})
    print(f"Simple 'Sí': {valid} (Expected True) - Val: {out.get('ha_trabajado_en_hermes')}")
    
    # Case 2: Complex Phrase (Should return False to trigger AI)
    # "hace tiempo" was hardcoded, now removed. Should return False (invalid) so AI takes over.
    valid, out, msg = bot._validate_and_extract_soft("trabajo_hermes", "hace tiempo trabajé allí", {})
    print(f"Complex Phrase: {valid} (Expected False to trigger AI) - Msg: {msg}")

    print("\n--- Testing Aptitude Logic ---")
    # Helper to test aptitude
    def check_apto(puesto_id, origen, expected_apto):
        data = {
            "edad": 25,
            "secundaria": True,
            "dni": True,
            "licencia": True,
            "disponibilidad": True,
            "puesto_id": puesto_id,
            "origen": origen
        }
        is_apto, reasons = bot._evaluate_aptitud(data)
        print(f"Puesto {puesto_id} ({origen}): Apto={is_apto} (Expected {expected_apto}) - Reasons: {reasons}")

    # 1. Agentes Chorrillos (Lima)
    check_apto(1, "lima", True)
    check_apto(1, "provincia", False)
    
    # 3. Bancos (Ambos)
    check_apto(3, "lima", True)
    check_apto(3, "provincia", True)
    
    # 4. Provincia (Provincia)
    check_apto(4, "lima", False)
    check_apto(4, "provincia", True)

if __name__ == "__main__":
    test_logic()
