---
name: reparto-tareas
description: División de archivos entre los dos integrantes del backend, para no colisionar en el mismo código el mismo día
metadata:
  type: project
---

**Última actualización:** 26 de agosto de 2026 (tarde — Persona 2 completó su línea).

Este archivo se actualiza cada vez que el equipo de backend se reparte trabajo entre varias
personas. Antes de tocar código, cualquier integrante (o su Claude) debe revisar esta sección
para saber en qué archivos puede trabajar sin generar conflictos de Git con el resto del equipo.

## Flujo de Git (nuevo, 26 ago)

Además de dividir por archivos, cada persona trabaja en su propia rama — **nadie commitea
directo sobre `main`**:

```bash
git checkout -b feature/lo-que-sea   # antes de empezar a tocar código
git add ... && git commit -m "..."   # normal, cuantas veces haga falta
git push -u origin feature/lo-que-sea  # respalda la rama en GitHub, no toca main
```

`main` solo se actualiza mergeando una rama con Pull Request cuando ese trabajo está listo.
Con esto, aunque las dos personas pusheen el mismo día, ninguna le "pisa" el `main` a la otra
ni fuerza un `git pull` a mitad de una sesión de trabajo. La rama de la sesión del 26 ago:
`feature/retos-ia-persona2` (pusheada, todavía sin PR/merge a `main`).

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

**✅ Completa (26 ago).** Ver diseño completo en `docs/pipeline_ia_retos.md` (diagrama del flujo
completo, ejemplo del reto WEP, y por qué la IA nunca genera el archivo directamente). Todo el
trabajo vive en la rama `feature/retos-ia-persona2` (pusheada a GitHub, sin mergear a `main`
todavía).

Archivos trabajados (en este orden):

1. ✅ `backend/app/schemas/challenge.py` — `ChallengeSpec` de Pydantic (id, difficulty, category,
   description, technique, flag, hint, solution), con `Literal` para el registro fijo y
   validación de formato de flag (`FLAG{...}`).
2. ✅ `backend/app/services/challenge_generator.py` — `TECHNIQUE_REGISTRY` con **las dos**
   técnicas del MVP: `iv_reuse_wep` (pcap real con Scapy, RC4 propio, IV reutilizado, flag en
   el payload) y `xor_singlebyte` (XOR de un solo byte). Las dos probadas simulando el ataque
   real, recuperando la flag sin conocer la llave de antemano.
3. ✅ `backend/app/services/ai_advisor.py` — llama a Together AI y devuelve el JSON crudo sin
   validar (prompting simple, sin fine-tuning todavía). Probado con un cliente Together
   simulado — **falta probarlo contra la API real** (necesita un `TOGETHER_API_KEY` real).
4. ✅ `challenges/templates/network/template.json` y `challenges/templates/crypto/template.json`
   — plantillas reales, validadas contra `ChallengeSpec` y contra los generadores.

**Extra no listado originalmente:** `backend/tests/unit/` — 25 tests con `unittest` (librería
estándar, sin tocar `requirements.txt`) cubriendo las 3 piezas de arriba. Correr con
`venv\Scripts\python.exe -m unittest discover -s tests/unit -v` desde `backend/`.

**Siguiente paso real para esta línea:** conseguir un `TOGETHER_API_KEY` propio y probar
`ai_advisor.py` contra la API real (ver qué tan bien el modelo respeta el formato del prompt);
después, abrir el Pull Request de `feature/retos-ia-persona2` hacia `main`.

**Setup necesario antes de empezar:**
* `git pull` para traer este reparto y el `requirements.txt` actualizado (ya incluye `scapy`).
* Crear su propio `backend/venv` e instalar con `pip install -r requirements.txt`.
* Copiar `backend/.env.example` a `backend/.env` y pedir el `TOGETHER_API_KEY` por un canal
  seguro (Discord, WhatsApp) — **nunca por Git**. No necesita `DATABASE_URL` real para este
  alcance de tareas; puede dejarlo como el placeholder de `.env.example` mientras no toque la
  base de datos.

**No tocar:** `app/db/`, `app/models/user.py`, `app/core/security.py`,
`app/api/v1/endpoints/auth.py`, `migrations/` — son de la Persona 1.

## Archivo compartido (ya resuelto de antemano)

`backend/requirements.txt` — se agregó `scapy==2.6.1` de una vez antes de repartir las tareas,
específicamente para que ninguna de las dos personas necesite tocar este archivo hoy y generar
un conflicto de Git al hacer merge. Persona 1 sí lo tocó después (26 ago, directo a `main`) para
subir `psycopg2-binary` de 2.9.10 a 2.9.12 (soporte para Python 3.14) — sin conflicto porque
Persona 2 nunca lo tocó desde su rama. Por las dudas: si en algún momento las dos personas
necesitan cambiar `requirements.txt` el mismo día, coordinar por Discord/WhatsApp antes de
tocarlo, no asumir que sigue "resuelto de antemano".

Ver también: [[project-context]]
