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
* El venv del backend debe crearse con **Python 3.12**, no la versión más nueva instalada en la
  máquina (ej. 3.14) — `psycopg2-binary` no tenía wheel para 3.14 en Windows al 26 ago 2026 y
  falla al compilar desde código fuente sin PostgreSQL local instalado. El equipo subió
  `psycopg2-binary==2.9.12` para intentar arreglar esto, pero sin confirmar aún con una
  instalación real en 3.14.
* Nadie del equipo commitea directo a `main` — cada persona trabaja en su propia rama
  (`feature/<algo>`) y junta a `main` con Pull Request. Detalle y comandos en
  `.claude/memory/reparto_tareas.md`.

**Por qué importa:** estas decisiones ya resolvieron ambigüedades que se discutieron a propósito.
Si una sugerencia futura (propia o de otra IA, ej. ChatGPT/Gemini) reintroduce Fargate, ALB,
fine-tuning de Llama, o Docker local por usuario, señalar que ya se evaluó y por qué se descartó
antes de proceder — no tratarlo como una idea nueva sin más.

Ver también: [[user-profile]]
