import os, smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_MODE = os.getenv("SMTP_MODE", "starttls").lower()  # starttls | ssl
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_TO   = os.getenv("SMTP_TO", "")

if not (SMTP_HOST and SMTP_PORT and SMTP_FROM and SMTP_TO):
    raise SystemExit("Faltan SMTP_HOST, SMTP_PORT, SMTP_FROM o SMTP_TO en .env")

msg = EmailMessage()
msg["From"] = SMTP_FROM
msg["To"] = SMTP_TO
msg["Subject"] = "Prueba SMTP – Chatbot TI"
msg.set_content("Hola Eduardo,\n\nEste es un correo de prueba desde el bot.\n\n—Bot TI")

try:
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
    print("✅ Correo de prueba enviado a", SMTP_TO)
except Exception as e:
    print("❌ Error enviando correo:", e)
