# 🤖 Hermes ReclutaBot — Bot de Reclutamiento por WhatsApp

Bot de reclutamiento automatizado para **Hermes Transportes Blindados**, integrado con WhatsApp a través de [WAHA](https://waha.devlike.pro/) y potenciado por Google Gemini.

El sistema guía a los postulantes a través de un cuestionario estructurado por WhatsApp, evalúa su aptitud automáticamente según reglas de negocio y agenda entrevistas presenciales para los candidatos aptos.

---

## 📋 Tabla de Contenidos

- [Arquitectura](#-arquitectura)
- [Flujo de Preguntas](#-flujo-de-preguntas)
- [Reglas de Aptitud](#-reglas-de-aptitud-aptos-vs-no-aptos)
- [Catálogo de Puestos](#-catálogo-de-puestos)
- [Instrucciones a Gemini (IA)](#-instrucciones-a-gemini-ia)
- [Configuración y Despliegue](#-configuración-y-despliegue)
- [Variables de Entorno](#-variables-de-entorno)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [API Endpoints](#-api-endpoints)

---

## 🏗 Arquitectura

```
┌──────────────┐     Webhook     ┌──────────────┐     Supabase
│   WhatsApp   │ ──────────────► │   Flask API   │ ──────────────► BD
│   (WAHA)     │ ◄────────────── │   (ai_bot)    │
│   Puerto 3000│    Respuesta    │  Puerto 5006  │     Gemini
└──────────────┘                 └──────┬───────┘ ──────────────► IA
                                        │
                                   Docker Compose
```

| Componente | Tecnología | Función |
|---|---|---|
| **WAHA** | Docker (`devlikeapro/waha:noweb`) | Gateway WhatsApp ↔ HTTP |
| **API** | Python 3.10 / Flask | Lógica del bot, procesamiento de mensajes |
| **IA** | Google Gemini 2.5 Flash + Pro (fallback) | Validación de respuestas ambiguas, chat post-postulación |
| **BD** | Supabase (PostgreSQL) / JSON local (fallback) | Almacenamiento de postulantes |

---

## 📝 Flujo de Preguntas

El bot realiza **~20 preguntas** al postulante. Algunas son condicionales según respuestas previas:

| # | Pregunta | Campo | Condicional |
|---|---|---|---|
| 0 | Consentimiento de datos personales | `autorizacion_datos` | — |
| 1 | Nombres (sin apellidos) | `nombre` | — |
| 2 | Apellidos | `apellidos` | — |
| 3 | Edad | `edad` | — |
| 4 | Género | `genero` | — |
| 5 | Tipo de documento (DNI / CE) | `tipo_documento` | — |
| 6 | Número de documento | `numero_documento` | — |
| 7 | Teléfono de contacto | `telefono` | — |
| 8 | Correo electrónico | `correo` | — |
| 9 | Grado de instrucción (Sec. completa/incompleta) | `secundaria` | — |
| 10 | ¿Ha trabajado en Hermes antes? | `trabajo_hermes` | — |
| 11 | Modalidad de trabajo (completo/medio/intermitente) | `modalidad` | — |
| 12 | Distrito donde vive | `distrito` | — |
| 13 | Lugar de residencia (Lima / Provincia) | `lugar_residencia` | — |
| 14 | Nombre de la provincia | `ciudad` | Solo si eligió **Provincia** |
| 15 | ¿Tiene licencia de conducir? | `licencia` | — |
| 16 | Tipo de licencia (A1, A2B, BII, etc.) | `licencia_tipo` | Solo si **tiene licencia** |
| 17 | Puesto al que postula (lista de 18) | `puesto` | — |
| 18a | Especificar puesto | `puesto_otros` | Solo si Puesto = **Otros** |
| 18b | Sucursal Minería | `puesto_mineria_sucursal` | Solo si Puesto = **12 o 13** (Minería) |
| 19 | ¿Disponibilidad inmediata? | `disponibilidad` | — |
| 20 | Medio de captación | `medio_captacion` | — |
| 20b | Especificar medio | `medio_captacion_otro` | Solo si Medio = **Otros** |
| 21 | Confirmación de entrevista (fecha/hora) | `confirmacion_entrevista` | Solo si es **APTO** |

### Flujo Visual

```
Inicio ("empezar")
  │
  ├── Consentimiento de Datos ──► Si rechaza → Fin
  │
  ├── Preguntas 1-20 (secuenciales, con validación)
  │
  ├── Evaluación de Aptitud
  │     ├── APTO → Proponer fecha de entrevista → Confirmar → Fin exitoso
  │     └── NO APTO → Mensaje de agradecimiento → Fin
  │
  └── Post-conversación (chat libre con Gemini)
```

---

## ✅ Reglas de Aptitud (Aptos vs No Aptos)

Al finalizar el cuestionario, el bot evalúa automáticamente si el postulante cumple con **todos** los criterios. Un solo criterio no cumplido = **NO APTO**.

### Criterios de Evaluación

| # | Criterio | Regla | Resultado si no cumple |
|---|---|---|---|
| 1 | **Edad** | Entre 18 y 50 años | ❌ No apto |
| 2 | **Ubicación vs Puesto** | Debe coincidir: puestos de Lima → vive en Lima; puestos de Provincia → vive en Provincia; puestos "Ambos" → acepta cualquiera | ❌ No apto |
| 3 | **Ubicación Minería** (puestos 12 y 13) | La provincia de residencia debe coincidir con la sucursal elegida (ej: vive en La Libertad → sucursal Trujillo ✅). Usa Gemini para match semántico si no hay coincidencia directa | ❌ No apto |
| 4 | **Secundaria** | Debe tener secundaria completa | ❌ No apto |
| 5 | **Tipo de Documento** | Solo DNI. Carné de Extranjería no aceptado | ❌ No apto |
| 6 | **Licencia** (puestos 8 y 9) | Conductores y Motorizados **deben** tener licencia | ❌ No apto |
| 7 | **Disponibilidad** | Debe tener disponibilidad inmediata | ❌ No apto |

### Regla de Ubicación por Puesto

| Puesto | Ubicación requerida |
|---|---|
| Agentes de Seguridad Chorrillos (1) | Lima |
| Agentes Traslado Valores (2) | Lima |
| Agentes Seguridad Bancos (3) | Ambos |
| Agentes Seguridad Provincia (4) | Provincia |
| Operarios Carga y Descarga (5) | Ambos |
| Cajeros (6) | Ambos |
| Coordinadores/Encargados (7) | Lima |
| Conductores/Choferes (8) | Lima |
| Motorizados BII (9) | Lima |
| Operarios Limpieza (10) | Lima |
| Despachadores (11) | Lima |
| Agentes Seguridad Minería (12) | Provincia |
| Supervisores Minería (13) | Provincia |
| Técnico Electrónico (14) | Lima |
| Mecánico Automotriz (15) | Lima |
| Técnico Electricista (16) | Lima |
| Digitadores (17) | Lima |
| Otros (18) | Ambos |

### Resultado para el postulante

- **APTO**: Se le propone fecha de entrevista presencial (Full Day). Si confirma, se agenda automáticamente calculando el siguiente día hábil con aforo disponible (máx. 40 por día).
- **NO APTO**: El bot **nunca le dice que fue rechazado**. Recibe un mensaje de agradecimiento indicando que su perfil fue registrado y será evaluado.

---

## 📦 Catálogo de Puestos

| ID | Puesto |
|---|---|
| 1 | Agentes de Seguridad Chorrillos |
| 2 | Agentes de Traslado de Valores Chorrillos |
| 3 | Agentes de Seguridad para Bancos |
| 4 | Agentes de Seguridad Provincia |
| 5 | Operarios de Carga y Descarga |
| 6 | Cajeros (Atención al Cliente) |
| 7 | Coordinadores / Encargados de Caja |
| 8 | Conductores / Choferes (A1 - A2B) |
| 9 | Motorizados BII |
| 10 | Operarios de Limpieza |
| 11 | Despachadores |
| 12 | Agentes de Seguridad - Minería |
| 13 | Supervisores Operativos - Minería |
| 14 | Técnico Electrónico |
| 15 | Mecánico Automotriz |
| 16 | Técnico Electricista |
| 17 | Digitadores |
| 18 | Otros |

Para los puestos de **Minería (12 y 13)**, se presenta un sub-menú de sucursales: Arequipa, Trujillo, Huánuco, Cusco u Otros.

---

## 🧠 Instrucciones a Gemini (IA)

### System Instruction (Base)

Aplica a **todas** las llamadas de Gemini:

```
Eres "Hermes ReclutaBot", asistente de reclutamiento automatizado de Hermes Transportes Blindados.

🎯 OBJETIVO: Evaluar postulantes, filtrar si son aptos e invitarlos a entrevista.

🚫 GUARDRAILS:
1. Solo extracción de datos y orientación sobre la postulación.
2. Ante temas ajenos → "Soy un asistente de Reclutamiento de Hermes."
3. NO inventes horarios ni cambies reglas.
4. Cuando se pida JSON, responde SOLO con JSON.
```

### Modelo y Fallback

| Rol | Modelo | Uso |
|---|---|---|
| **Primario (rápido)** | `gemini-2.5-flash` | Validación de respuestas, extracción de datos |
| **Respaldo (robusto)** | `gemini-2.5-pro` | Se activa si Flash falla 2 veces consecutivas |

**Flujo de retry**: Flash (intento 1) → pausa 1.5s → Flash (intento 2) → Pro (fallback) → `None` (fallback determinista).

### Prompt Post-Postulación

Cuando el postulante completa el cuestionario y sigue escribiendo, Gemini responde con estas reglas:

```
1. SIEMPRE responde directamente a la pregunta del usuario primero.
2. Usa el contexto del candidato para info precisa. Si la entrevista 
   YA fue agendada, NO digas "te contactaremos para agendar".
3. Dudas operativas desconocidas → "Esos detalles te los brindará RRHH."
4. NO inventes información, NO cambies fechas/horarios.
5. Tono cálido, breve, profesional. Sin "¡Hola!" si no te saludan.

ANTI-REPETICIÓN:
- NO repitas datos de la entrevista en cada respuesta.
- Solo menciona fecha/lugar/documentos si la pregunta es sobre eso.
- "ok"/"gracias" → respuesta breve (1 línea), sin repetir info.

CANDIDATOS EN EVALUACIÓN:
- NUNCA digas que "no fue aceptado" o "no cumple requisitos".
- Comunica que su perfil está siendo evaluado por RRHH.
```

---

## ⚙ Configuración y Despliegue

### Requisitos

- Docker y Docker Compose
- API Key de Google Gemini
- Cuenta de Supabase (opcional, fallback a JSON local)

### Despliegue con Docker

```bash
# Opción 1: Desde código fuente
git clone https://github.com/eportaro/proyecto_waha_htb.git
cd proyecto_waha_htb
docker compose up -d --build

# Opción 2: Desde imágenes .tar (entorno sin internet)
docker load -i api-hermes.tar
docker load -i waha-noweb.tar
# Colocar .env y docker-compose.yml en la misma carpeta
docker compose up -d
```

### Verificar que está funcionando

```bash
docker logs wpp-api-htb --tail 10
# Debe mostrar:
# ✅ Supabase conectado
# ✅ Gemini inicializado: gemini-2.5-flash
# ✅ WAHA conectado correctamente: 200
# ✅ Servicios iniciados correctamente
```

---

## 🔑 Variables de Entorno

| Variable | Descripción | Default |
|---|---|---|
| `PORT` | Puerto de la API Flask | `5006` |
| `FLASK_DEBUG` | Modo debug | `1` |
| `WAHA_API_URL` | URL del servicio WAHA | `http://waha:3000` |
| `WAHA_API_KEY` | API Key de WAHA | — |
| `WEBHOOK_URL` | URL del webhook (para que WAHA envíe mensajes) | — |
| `GOOGLE_API_KEY` | API Key de Google Gemini | — |
| `GEMINI_MODEL` | Modelo principal | `gemini-2.5-flash` |
| `GEMINI_FALLBACK_MODEL` | Modelo de respaldo | `gemini-2.5-pro` |
| `GEMINI_TEMPERATURE` | Temperatura de generación | `0.0` |
| `GEMINI_MAX_TOKENS` | Máximo tokens de respuesta | `600` |
| `SUPABASE_URL` | URL del proyecto Supabase | — |
| `SUPABASE_KEY` | Service Role Key (JWT) | — |
| `SESSION_TIMEOUT_MINUTES` | Timeout de sesión inactiva | `60` |
| `COOLDOWN_HOURS` | Horas antes de poder reiniciar postulación | `24` |

---

## 📁 Estructura del Proyecto

```
proyecto_waha_last/
├── app.py                  # Flask app, webhook, API endpoints
├── database.py             # Supabase + JSON local, evaluación de aptitud
├── requirements.txt        # Dependencias Python
├── Dockerfile.api          # Dockerfile para el servicio API
├── docker-compose.yml      # Orquestación WAHA + API
├── .env                    # Variables de entorno (no versionado)
├── bot/
│   ├── ai_bot.py           # Lógica del bot: flujo, validación, preguntas
│   └── gemini_client.py    # Cliente Gemini: retry, fallback, prompts
└── data/
    └── postulantes.json    # Almacenamiento local (fallback si no hay Supabase)
```

---

## 🌐 API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/chatbot/health` | Health check |
| `POST` | `/chatbot/webhook` | Recepción de mensajes de WAHA |
| `GET` | `/chatbot/postulantes` | Lista de postulantes (JSON) |
| `GET` | `/chatbot/postulantes/<phone>` | Detalle de un postulante |
| `GET` | `/chatbot/stats` | Estadísticas generales |
| `GET` | `/chatbot/sessions` | Sesiones activas |
