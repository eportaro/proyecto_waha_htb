# Chatbot TI HTB

## Descripción
Este proyecto implementa un chatbot para la automatización de procesos de reclutamiento y selección, integrado con WhatsApp a través de WAHA (WhatsApp HTTP API) y potenciado por Inteligencia Artificial (Google Gemini).

El sistema permite gestionar postulaciones, responder preguntas frecuentes y guiar a los candidatos a través de un flujo conversacional, almacenando la información en una base de datos (Supabase o local).

## Características Principales
- **Integración con WhatsApp:** Uso de WAHA para envío y recepción de mensajes.
- **Inteligencia Artificial:** Integración con Google Gemini para procesamiento de lenguaje natural.
- **Flujo de Reclutamiento:** Automatización de preguntas de filtro y recolección de datos de candidatos.
- **Gestión de Postulantes:** Almacenamiento y consulta de datos de postulantes.
- **API REST:** Endpoints para consulta de estado, estadísticas y detalles de postulantes.

## Requisitos Previos
- Python 3.8+
- Docker (opcional, para despliegue con contenedores)
- Cuenta de Supabase (opcional, si se usa como base de datos)
- API Key de Google Gemini

## Instalación

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/eportaro/chatbot_ti_htb.git
    cd chatbot_ti_htb
    ```

2.  **Crear y activar un entorno virtual:**
    ```bash
    python -m venv venv
    # En Windows:
    venv\Scripts\activate
    # En Linux/Mac:
    source venv/bin/activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar variables de entorno:**
    Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:
    ```env
    PORT=5006
    FLASK_DEBUG=1
    # Agrega aquí tus otras claves (SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, WAHA_API_URL, etc.)
    ```

## Uso

### Ejecución Local
Para iniciar la aplicación localmente:
```bash
python app.py
```
El servidor se iniciará en `http://localhost:5006` (o el puerto definido en `.env`).

### Docker
Si prefieres usar Docker:
```bash
docker-compose up --build
```

## Estructura del Proyecto
- `app.py`: Punto de entrada de la aplicación Flask y definición de rutas.
- `bot/`: Lógica del bot y manejo de conversaciones con IA.
- `services/`: Integraciones con servicios externos (WAHA, Base de Datos).
- `data/`: Almacenamiento de datos locales (si aplica).
- `requirements.txt`: Dependencias del proyecto.

## Contribución
1.  Haz un Fork del proyecto.
2.  Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
3.  Haz Commit de tus cambios (`git commit -m 'Agrega nueva funcionalidad'`).
4.  Haz Push a la rama (`git push origin feature/nueva-funcionalidad`).
5.  Abre un Pull Request.
