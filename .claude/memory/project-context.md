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
* Auth con verificación de correo (MFA) decidida el 13 sep: registro **y** login exigen un
  código de 6 dígitos enviado al correo (doble capa). El modelo `User` se amplía con
  `full_name`, `gender`, `role` (estudiante/profesor/admin); el `username` se reutiliza como
  handle. El rol se deriva del dominio institucional y cualquier otro correo entra como
  estudiante. Envío por `smtplib` con fallback a modo dev; códigos en memoria (MVP de una sola
  instancia). Estas funciones se prototiparon por error en un frontend Node aparte
  (`wispr_terminal_professional`) y se **migran a FastAPI** (trabajo de Persona 1, no toca
  archivos de Persona 2). El Workspace del colegio rechaza correo externo (rebote 550): para
  correos institucionales hará falta lista blanca o SMTP interno del colegio. Detalle en
  `CLAUDE.md`.

**Por qué importa:** estas decisiones ya resolvieron ambigüedades que se discutieron a propósito.
Si una sugerencia futura (propia o de otra IA, ej. ChatGPT/Gemini) reintroduce Fargate, ALB,
fine-tuning de Llama, o Docker local por usuario, señalar que ya se evaluó y por qué se descartó
antes de proceder — no tratarlo como una idea nueva sin más.

Ver también: [[user-profile]]
