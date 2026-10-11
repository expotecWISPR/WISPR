---
name: project-context
description: Estado y decisiones de arquitectura del proyecto WISPR (backend, AWS, Supabase, Together AI)
metadata:
  type: project
---

WISPR es una plataforma CTF educativa (CTP Don Bosco, EXPOTEC octubre 2026). El detalle completo
de tecnologías, arquitectura y progreso vive en `CLAUDE.md` (raíz del repo), sección
"Estado actual del proyecto" — se actualiza al final de cada sesión de trabajo.

Decisiones clave a recordar:

* Supabase = solo PostgreSQL. El JWT se implementa manualmente en el backend, no con Supabase Auth.
* El sandbox de retos (Docker) es centralizado en AWS y compartido entre usuarios, no corre local
  en la máquina de cada estudiante.
* AWS: arquitectura MVP de una sola instancia EC2 (`docs/arquitectura_mvp.md`), sin NAT Gateway.
  La versión de 3 subredes (`docs/arquitectura_produccion.md`) es solo referencia para la defensa
  ante el profesor, no lo que se despliega.
* IA: Together AI + Llama 3.3 70B, ajustado con **LoRA** (no fine-tuning completo — ese sí se
  descartó por costo/GPU). La IA genera la *especificación* de nuevos retos (JSON: narrativa,
  flag, técnica, dificultad), validada con Pydantic contra un registro fijo de técnicas — nunca
  genera el archivo/binario directamente ni inventa mecanismos nuevos. Detalle completo en
  `docs/pipeline_ia_retos.md`. Dataset de ~500 ejemplos curado por un compañero del equipo.
* Redis, Celery y MinIO fueron evaluados y descartados explícitamente.
* Auth con verificación de correo (MFA) decidida el 13 sep, **migrada a FastAPI el 7 oct**:
  registro **y** login exigen un código de 6 dígitos enviado al correo (doble capa). El modelo
  `User` se amplió con `full_name`, `gender`, `role` (estudiante/profesor/admin); el `username`
  se reutiliza como handle. El rol se deriva del dominio institucional y cualquier otro correo
  entra como estudiante. Envío por `smtplib` con fallback a modo dev; códigos en memoria (MVP
  de una sola instancia). Sesiones **revocables respaldadas en Supabase** (token opaco + hash
  SHA-256 en una tabla), no JWT — decisión del 7 oct, para poder revocar de verdad al cerrar
  sesión o bloquear una cuenta. Rutas montadas en `/api/players/*` (sin prefijo `/v1`) para
  calzar exacto con lo que ya llama el frontend `wispr_terminal_professional` (prototipo Node
  fuera de este repo, de donde se migró la lógica real). Pendiente: aplicar la migración de
  Alembic y probar contra Supabase reactivado. Detalle en `CLAUDE.md`.
* `feature/retos-ia-persona2` se fusionó a `main` el 7 oct: el pipeline de generación de retos
  con IA (`ChallengeSpec`, `TECHNIQUE_REGISTRY` con `iv_reuse_wep`/`xor_singlebyte`,
  `ai_advisor.py`, templates, 25 tests) ya es código real en `main`, no solo diseño. Decisión
  del mismo día: el fine-tuning con LoRA queda en pausa (se está resolviendo por separado) y
  mientras tanto `ai_advisor.py` usa el modelo base de Together AI por **prompting simple**.
* Python del venv: 3.12, 3.13 o 3.14. Verificado el 11 oct que `psycopg2-binary==2.9.12` (el
  de `requirements.txt`) tiene wheels `win_amd64` para las tres — importa porque la mayoría del
  equipo/usuarios usa Windows. Si se sube la versión de psycopg2 o de Python, volver a verificar
  con `pip download --only-binary=:all: --platform win_amd64 --python-version 3XX`.
* Política de equipo (26 ago): nadie commitea directo a `main`, cada persona trabaja en su
  rama `feature/<algo>` y junta con Pull Request. En la práctica esto no se cumplió entre el 26
  ago y el 7 oct porque esta regla vivía solo en la rama sin fusionar — Persona 1 siguió
  commiteando directo a `main`. Vale la pena re-confirmarla con el equipo ahora que ya está
  fusionada, no asumir que se retoma sola.

**Por qué importa:** estas decisiones ya resolvieron ambigüedades que se discutieron a propósito.
Si una sugerencia futura (propia o de otra IA, ej. ChatGPT/Gemini) reintroduce Fargate, ALB,
fine-tuning de Llama, o Docker local por usuario, señalar que ya se evaluó y por qué se descartó
antes de proceder — no tratarlo como una idea nueva sin más.

Ver también: [[user-profile]]
