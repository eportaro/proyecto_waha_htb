import os, smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# Configuración SMTP
SMTP_HOST  = os.getenv("SMTP_HOST", "")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "587"))
SMTP_MODE  = os.getenv("SMTP_MODE", "starttls").lower()  # puede ser "ssl" o "starttls"
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
SMTP_FROM  = os.getenv("SMTP_FROM", SMTP_USER)  # por defecto, mismo que el usuario

def enviar_correo(asunto: str, cuerpo: str, destinatario: str):
    """Envía un correo usando la configuración SMTP al destinatario indicado."""
    if not SMTP_HOST or not SMTP_FROM or not destinatario:
        print("[WARN] Falta configuración SMTP o destinatario.")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.set_content(cuerpo)

        if SMTP_MODE == "ssl":
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                if SMTP_USER and SMTP_PASS:
                    s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                s.ehlo()
                s.starttls()
                if SMTP_USER and SMTP_PASS:
                    s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)

        print(f"[OK] Correo enviado a {destinatario}")
        return True
    except Exception as e:
        print("[ERR] Falló envío de correo:", e)
        return False
