---
name: reparto-tareas
description: División de archivos entre los dos integrantes del backend, para no colisionar en el mismo código el mismo día
metadata:
  type: project
---

**Última actualización:** 26 de agosto de 2026.

Este archivo se actualiza cada vez que el equipo de backend se reparte trabajo entre varias
personas. Antes de tocar código, cualquier integrante (o su Claude) debe revisar esta sección
para saber en qué archivos puede trabajar sin generar conflictos de Git con el resto del equipo.

## Contexto

El backend ahora lo trabajan dos personas. Se dividió el trabajo en dos líneas que **no
comparten archivos entre sí**, elegidas así a propósito:

* La línea de Usuarios/Autenticación necesita la conexión real a Supabase (`DATABASE_URL`),
  que solo tiene configurada la persona dueña de esa cuenta.
* La línea de generación de retos con IA no toca la base de datos todavía — solo necesita un
  `TOGETHER_API_KEY` propio (cada quien pide el suyo en api.together.ai, no se comparte por Git).

## Persona 1 — Usuarios y Autenticación

Ver diseño completo en `CLAUDE.md` (sección "IA" y checkpoint) y en la sesión donde se armó
`app/core/config.py` (ya implementado y probado).

Archivos a trabajar (en este orden):

1. `backend/app/db/base.py` — declarar la `Base` de SQLAlchemy e importar los modelos para que
   Alembic los detecte automáticamente.
2. `backend/app/db/session.py` — crear el `engine` y la función `get_db()` que FastAPI inyecta
   en los endpoints.
3. `backend/app/models/user.py` — el modelo `User` (id, email, password_hash, points,
   created_at, etc.).
4. `backend/migrations/alembic.ini` y `backend/migrations/env.py` — conectar Alembic a
   `settings.DATABASE_URL` (desde `app/core/config.py`) y a `Base.metadata`.
5. Generar y aplicar la primera migración (crea la tabla `users` real en Supabase).
6. `backend/app/core/security.py` — hash de contraseñas con bcrypt, crear y verificar JWT.
7. `backend/app/schemas/user.py` — esquemas de entrada/salida (registro, login, perfil público).
8. Si alcanza el tiempo: `backend/app/api/v1/endpoints/auth.py` — endpoints de registro/login.

**No tocar:** `app/schemas/challenge.py`, `app/services/challenge_generator.py`,
`app/services/ai_advisor.py`, `challenges/templates/` — son de la Persona 2.

## Persona 2 — Generación de retos con IA

Ver diseño completo en `docs/pipeline_ia_retos.md` (diagrama del flujo completo, ejemplo del
reto WEP, y por qué la IA nunca genera el archivo directamente).

Archivos a trabajar (en este orden):

1. `backend/app/schemas/challenge.py` — el `ChallengeSpec` de Pydantic (campos: id, difficulty,
   category, description, technique, flag, hint, solution — ver el ejemplo JSON en
   `docs/pipeline_ia_retos.md`).
2. `backend/app/services/challenge_generator.py` — el `TECHNIQUE_REGISTRY` (diccionario técnica
   → función generadora) y la primera función real: `iv_reuse_wep`, usando Scapy, con el reto
   WEP de ejemplo (IVs repetidos, flag embebida en el payload ARP).
3. `backend/app/services/ai_advisor.py` — la función que llama a Together AI y devuelve el JSON
   crudo (sin validar todavía — la validación la hace el schema del paso 1). Se puede empezar
   con prompting simple; no hace falta esperar a que el fine-tuning con LoRA esté listo.
4. `challenges/templates/network/template.json` — llenar la plantilla real con el ejemplo del
   reto WEP.

**Setup necesario antes de empezar:**
* `git pull` para traer este reparto y el `requirements.txt` actualizado (ya incluye `scapy`).
* Crear su propio `backend/venv` e instalar dependencias. **Los comandos difieren según el
  sistema operativo** — el `.vscode/settings.json` del repo NO fija un intérprete por defecto
  a propósito, justamente porque esta ruta no es la misma en los dos sistemas:

  | Paso | Windows (cmd o PowerShell) | Mac / Linux |
  |---|---|---|
  | Crear el venv | `python -m venv venv` | `python3 -m venv venv` |
  | Instalar dependencias | `venv\Scripts\pip install -r requirements.txt` | `venv/bin/pip install -r requirements.txt` |
  | Ruta del intérprete para VS Code | `backend\venv\Scripts\python.exe` | `backend/venv/bin/python3` |

  En Windows, `python3` normalmente no existe como comando — es `python` a secas. Y la carpeta
  se llama `Scripts\`, no `bin/`. Si algo de esto falla, probablemente es por usar el comando
  del sistema operativo equivocado.
* En VS Code, correr `Python: Select Interpreter` y elegir el que VS Code detecte
  automáticamente en `backend/venv` (normalmente aparece solo, sin tener que escribir la ruta
  a mano, una vez que el `venv` ya existe).
* Copiar `backend/.env.example` a `backend/.env` y pedir el `TOGETHER_API_KEY` por un canal
  seguro (Discord, WhatsApp) — **nunca por Git**. No necesita `DATABASE_URL` real para este
  alcance de tareas; puede dejarlo como el placeholder de `.env.example` mientras no toque la
  base de datos.

**No tocar:** `app/db/`, `app/models/user.py`, `app/core/security.py`,
`app/api/v1/endpoints/auth.py`, `migrations/` — son de la Persona 1.

## Archivo compartido (ya resuelto de antemano)

`backend/requirements.txt` — se agregó `scapy==2.6.1` de una vez antes de repartir las tareas,
específicamente para que ninguna de las dos personas necesite tocar este archivo hoy y generar
un conflicto de Git al hacer merge.

Ver también: [[project-context]]
