---
name: reparto-tareas
description: División de archivos entre los dos integrantes del backend, para no colisionar en el mismo código el mismo día
metadata:
  type: project
---

> **⚠️ Ya no aplica (11 oct 2026):** el reparto por archivos terminó. La Persona 1 lleva todo el
> backend y la Persona 2 trabaja en AWS. Este archivo queda como registro histórico; la nota de
> Supabase pausado de abajo sigue siendo útil.

**Última actualización:** 7 de octubre de 2026 (fusión de `feature/retos-ia-persona2` a `main`).

**Nota recurrente — Supabase se pausa solo:** el proyecto está en el plan gratuito de Supabase,
que pausa la base de datos después de varios días sin actividad. Ya pasó dos veces. Si algo que
antes funcionaba de repente da `could not translate host name ... to address` al conectar, no es
un bug de código — entrá a supabase.com, abrí el proyecto, y hacé clic en "Restore project"
(tarda 1-2 minutos). Revisar esto **antes** de asumir que algo se rompió.

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
ni fuerza un `git pull` a mitad de una sesión de trabajo. La rama de la sesión del 26 ago,
`feature/retos-ia-persona2`, ya se fusionó a `main` (7 oct) — ver "Estado de la fusión" abajo.
**Nota:** esta regla vivió sin fusionar hasta el 7 oct, así que no se cumplió entre medio
(Persona 1 siguió commiteando directo a `main`); vale la pena re-confirmarla con el equipo.

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

1. ~~`backend/app/db/base.py`~~ ✅ Hecho.
2. ~~`backend/app/db/session.py`~~ ✅ Hecho.
3. ~~`backend/app/models/user.py`~~ ✅ Hecho.
4. ~~`backend/migrations/alembic.ini` y `env.py`~~ ✅ Hecho.
5. ~~Primera migración (tabla `users` en Supabase)~~ ✅ Hecho y verificado.
6. ~~`backend/app/core/security.py`~~ ✅ Hecho y probado (hash con `bcrypt` directo, no
   `passlib` — ver nota en `CLAUDE.md`).
7. ~~`backend/app/schemas/user.py`~~ ✅ Hecho y probado — `UserCreate`, `UserPublic`,
   `UserUpdate`, `Token`. Requirió agregar `email-validator` a `requirements.txt`.
8. ~~`backend/app/api/v1/endpoints/auth.py`~~ ✅ Código escrito (`register`, `login`,
   `get_current_user`), junto con `users.py` (`GET /users/me`), el router de
   `app/api/v1/__init__.py`, y `backend/main.py` (por primera vez el backend arranca de
   verdad). Pruebas unitarias de `security.py` automatizadas en `tests/unit/test_security.py`
   (6/6 pasan). **Pendiente:** probar el flujo completo registro→login→perfil contra la base de
   datos real — se cortó por Supabase pausado a mitad de la prueba. Próxima sesión: reactivar
   Supabase, correr `POST /register` → `POST /login` → `GET /users/me`, y borrar el usuario de
   prueba de la tabla `users` real al terminar.

9. ~~Migración de auth con MFA por correo + perfil ampliado~~ ✅ Código escrito y probado
   (7 oct): `app/models/user.py` ampliado, migración `27e315b1d2f6`, `app/services/email.py`,
   `app/core/sessions.py` + `app/models/session.py` (sesiones revocables, no JWT),
   `app/services/auth_flow.py`, `app/api/players.py` (rutas `/api/players/*`, reemplazan a
   `app/api/v1/endpoints/auth.py`/`users.py`, que se **eliminaron**). 59 tests pasan contra
   SQLite en memoria. **Pendiente real:** aplicar la migración y probar contra Supabase
   reactivado con correo real; ver detalle completo en `CLAUDE.md` (checkpoint 7 oct).

**No tocar:** `app/schemas/challenge.py`, `app/services/challenge_generator.py`,
`app/services/ai_advisor.py`, `challenges/templates/` — son de la Persona 2.

## Persona 2 — Generación de retos con IA

**✅ Completa (26 ago) y fusionada a `main` (7 oct).** Ver diseño completo en
`docs/pipeline_ia_retos.md` (diagrama del flujo completo, ejemplo del reto WEP, y por qué la IA
nunca genera el archivo directamente). Decisión del 7 oct: el fine-tuning con LoRA queda en
pausa (se resuelve por separado); mientras tanto `ai_advisor.py` sigue con prompting simple
contra el modelo base.

Archivos trabajados (en este orden):

1. ✅ `backend/app/schemas/challenge.py` — `ChallengeSpec` de Pydantic (id, difficulty, category,
   description, technique, flag, hint, solution), con `Literal` para el registro fijo y
   validación de formato de flag (`WISPR{...}`).
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
y agregar la lógica de reintento/respaldo (usar `xor_singlebyte` como técnica estática si
Together AI no responde o devuelve algo inválido) — hoy esa función solo propaga el error.

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

**No tocar:** `app/db/`, `app/models/user.py`, `app/models/session.py`, `app/core/security.py`,
`app/core/sessions.py`, `app/services/auth_flow.py`, `app/services/email.py`,
`app/api/players.py`, `migrations/` — son de la Persona 1.

## Estado de la fusión (merge)

**Hecha el 7 de octubre de 2026.** `feature/retos-ia-persona2` se revisó (sin conflictos de
código — las dos líneas nunca tocaron los mismos archivos, solo hubo que resolver a mano 3
archivos de documentación/memoria) y se fusionó a `main`. Pendiente: hacer `git push` de ese
merge (este entorno no tiene credenciales de GitHub configuradas) y repartir la siguiente tanda
de tareas entre los dos — ver "Pendiente" en `CLAUDE.md`.

## Archivo compartido (ya resuelto de antemano)

`backend/requirements.txt` — se agregó `scapy==2.6.1` de una vez antes de repartir las tareas,
específicamente para que ninguna de las dos personas necesite tocar este archivo hoy y generar
un conflicto de Git al hacer merge. Persona 1 sí lo tocó después (26 ago, directo a `main`) para
subir `psycopg2-binary` de 2.9.10 a 2.9.12 (soporte para Python 3.14) — sin conflicto porque
Persona 2 nunca lo tocó desde su rama. Por las dudas: si en algún momento las dos personas
necesitan cambiar `requirements.txt` el mismo día, coordinar por Discord/WhatsApp antes de
tocarlo, no asumir que sigue "resuelto de antemano".

Ver también: [[project-context]]
