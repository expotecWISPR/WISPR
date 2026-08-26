# PROJECT_CONTEXT.md

# Proyecto

Somos un equipo de estudiantes de undécimo año de la especialidad de Ciberseguridad del CTP Don Bosco, desarrollando un proyecto para EXPOTEC.

El proyecto consiste en una aplicación de escritorio que funciona como una plataforma educativa de tipo CTF (Capture The Flag), inspirada en plataformas como Hackrocks, adaptada a nuestros propios objetivos y arquitectura.

El objetivo es ofrecer un entorno unificado donde un estudiante pueda resolver retos de ciberseguridad sin necesidad de configurar múltiples herramientas o máquinas virtuales.

Mi rol en el trabajo es ingeniero de backend, por lo tanto soy el encargado de el funcionamiento interno y la base de datos, quiero usar tambien supabase para este, por lo tanto es importante 

---

# Objetivo

Crear una plataforma modular que permita:

* Resolver retos de ciberseguridad.
* Validar flags automáticamente.
* Llevar puntuación y progreso.
* Mostrar rankings.
* Analizar el desempeño del usuario.
* Adaptar la dificultad según su rendimiento.
* Ejecutar herramientas reales dentro de un entorno aislado.

La plataforma está enfocada principalmente en aprendizaje y evaluación.

---

# Filosofía del proyecto

No buscamos crear una copia de Kali Linux.

No buscamos crear una IA que genere cualquier reto desde cero.

No buscamos construir la plataforma más compleja posible.

Buscamos una plataforma estable, modular, escalable y demostrable.

La simplicidad tiene prioridad sobre la complejidad innecesaria.

Toda decisión técnica debe justificarse por el valor real que aporta al proyecto.

---

# Inspiración

La referencia principal es Hackrocks.

Se toma inspiración de conceptos como:

* categorías de retos,
* niveles de dificultad,
* sistema de flags,
* progresión del usuario,
* scoreboard,
* experiencia de aprendizaje.

La implementación será completamente propia.

---

# Generación de retos

Los retos no se generan libremente por IA sin control. El sistema combina dos capas:

1. **Especificación (IA):** un modelo de lenguaje (Together AI + Llama 3.3 70B, ajustado con
   LoRA) genera un JSON con los parámetros del reto — narrativa, descripción, pista, flag,
   dificultad y la técnica específica a usar.
2. **Materialización (determinista):** ese JSON se valida con un schema de Pydantic
   (`app/schemas/challenge.py`) y se pasa a un generador del equipo
   (`app/services/challenge_generator.py`), que construye el archivo o entorno real (ej. con
   Scapy) según la técnica indicada.

La IA **no inventa mecanismos nuevos.** Solo puede elegir la técnica de un **registro fijo**
de técnicas que el equipo ya programó y probó (ej. `iv_reuse_wep`, `xor_singlebyte`). Si el
modelo devuelve una técnica fuera del registro, o un JSON con forma inválida, la validación de
Pydantic lo rechaza antes de intentar generar nada — nunca se materializa un archivo o
contenedor sin pasar por esa validación.

Esto mantiene el objetivo original: variantes únicas con coherencia y control, pero ahora los
valores de esas variantes (incluida la narrativa y la flag) los decide un modelo entrenado en
vez de estar fijos en el código.

Para el MVP, el pipeline se implementa completo solo en 1-2 categorías (crypto y network son
las que ya tienen ejemplos curados); el resto usa retos estáticos hechos a mano.

Detalle completo del pipeline en `docs/pipeline_ia_retos.md`.

---

# IA

La IA tiene un rol de apoyo, no de control total del sistema.

Su función es:

* analizar desempeño,
* recomendar retos,
* ajustar dificultad,
* generar o modificar pistas,
* ayudar en la personalización,
* generar la especificación (narrativa, flag, parámetros y técnica) de nuevos retos, dentro de
  un registro fijo de técnicas ya construidas por el equipo.

La IA no reemplaza el motor de generación procedural: propone parámetros, el motor
determinista los materializa. Ningún archivo, contenedor o flag se genera sin pasar primero por
la validación de Pydantic. Detalle completo del flujo en `docs/pipeline_ia_retos.md`.

**Modelo y método:** Llama 3.3 70B Instruct Turbo vía Together AI, ajustado con **LoRA**
(no fine-tuning completo — se evaluó y se descartó por costo e infraestructura de GPU). El
dataset de entrenamiento tiene ~500 ejemplos curados por el equipo, repartidos en varias
categorías.

---

# Docker

Docker es el núcleo del laboratorio.

Las herramientas de ciberseguridad se ejecutan dentro de contenedores aislados.

La aplicación interactúa con dichos contenedores sin exponer directamente el sistema operativo del usuario.

---

# Terminal integrada

La aplicación incluye una terminal integrada.

Los comandos ejecutados por el usuario deben ejecutarse sobre el entorno del contenedor correspondiente.

El usuario no necesita abrir una máquina virtual externa.

---

# Tecnologías confirmadas

## Frontend

* React
* Tailwind CSS
* Chart.js

## Aplicación de escritorio

* Electron

## Terminal

* xterm.js
* node-pty

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic

## Base de datos

* PostgreSQL

## Contenedores

* Docker
* Docker Compose
* seccomp
* AppArmor
* Linux Namespaces

## Análisis de datos

* Pandas
* NumPy
* Matplotlib
* Scikit-learn

## Ciberseguridad

* Wireshark
* TShark
* Scapy
* Aircrack-ng

## Nube (AWS)

* Amazon S3 — almacenamiento de archivos de retos (capturas .pcap, binarios, imágenes). Reemplaza a MinIO.
* AWS IAM — permisos y roles de acceso mínimos a los servicios AWS usados.
* Amazon CloudWatch — logging básico del backend (solo la capa gratuita por ahora).
* Amazon EC2 — una sola instancia (nginx + FastAPI + Docker host de retos) para el MVP.

AWS Fargate y Application Load Balancer se evaluaron y se descartaron para el MVP por costo y
complejidad innecesaria a esta escala (ver `docs/arquitectura_mvp.md`).

## Inteligencia artificial (generación de retos y recomendación)

* Together AI — proveedor de inferencia y de fine-tuning administrado.
* Llama 3.3 70B Instruct Turbo — modelo base, ajustado con **LoRA** vía el servicio de
  fine-tuning administrado de Together AI (no se gestiona infraestructura GPU propia). Dataset
  curado por el equipo (~500 ejemplos, varias categorías).
* El **fine-tuning completo** (reentrenar todos los parámetros del modelo) se evaluó y se
  descartó: requiere GPUs dedicadas y días de entrenamiento, inviable con los recursos del
  equipo. LoRA es viable porque solo entrena una fracción pequeña de los parámetros y corre
  como servicio administrado.
* Usos: generar la especificación de nuevos retos (narrativa, flag, técnica, dificultad — ver
  `docs/pipeline_ia_retos.md`), recomendaciones de retos, ajuste de dificultad y pistas.

---

# Tecnologías en evaluación

Estas tecnologías no son obligatorias.

Solo deben incorporarse si aparece una necesidad técnica demostrable durante el desarrollo.

* hcxdumptool

---

# Tecnologías descartadas

Se evaluaron y se decidió no usarlas. No reintroducir sin una justificación técnica nueva.

* Redis — sin necesidad demostrada a la escala del MVP.
* Celery — sin tareas en segundo plano que lo justifiquen todavía.
* MinIO — reemplazado por Amazon S3 (el proyecto ya usa AWS para almacenamiento de objetos).
* LLM genérico — resuelto: se usa específicamente Together AI + Llama 3.3 70B.
* Fine-tuning completo (reentrenar todos los parámetros) — inviable por GPU/tiempo. Se usa
  **LoRA** en su lugar (fine-tuning parcial, vía servicio administrado de Together AI).

---

# Estado actual del proyecto (checkpoint de sesión)

Esta sección se actualiza al final de cada sesión de trabajo para retomar el contexto completo
desde cualquier dispositivo, ya que este archivo viaja con el repositorio Git.

**Última actualización:** 26 de agosto de 2026 (sesión de Persona 2 — generación de retos con IA).

## Decisiones de arquitectura tomadas

* Supabase se usa **solo como base de datos PostgreSQL**. La autenticación JWT se implementa
  en el backend (`app/core/security.py`), no con el sistema de Auth nativo de Supabase.
* El sandbox de retos (Docker) es **centralizado en AWS**, compartido por todos los usuarios —
  no corre localmente en la máquina de cada estudiante. Cada contenedor se limita en memoria y
  CPU (`--memory`, `--cpus` de Docker) para no afectar a otros usuarios en la misma instancia.
* Arquitectura AWS del MVP: **una sola instancia EC2** (nginx + FastAPI + Docker host juntos),
  subred pública, un Security Group como único firewall, sin NAT Gateway ni subredes privadas.
  Detalle completo en `docs/arquitectura_mvp.md`.
* También existe `docs/arquitectura_produccion.md`: arquitectura de nivel empresarial (3
  subredes, NAT Gateway, Defensa en Profundidad) documentada como referencia/objetivo para la
  defensa ante el profesor — **no es la que se despliega** durante el desarrollo.
* La instancia EC2 se enciende solo durante sesiones de trabajo y se detiene (Stop, no
  Terminate) al terminar, para minimizar costo. El presupuesto de $300-400 USD es el **total
  del proyecto** hasta EXPOTEC, no un monto mensual recurrente.
* Es **Linux Namespaces**, no "Docker Namespaces" — Docker usa Linux Namespaces internamente,
  no es una tecnología separada.
* **Generación de retos con IA (nuevo, 11 ago):** un modelo (Llama 3.3 70B + LoRA, vía
  Together AI) genera la especificación del reto (JSON: narrativa, flag, técnica, dificultad).
  Se valida con Pydantic contra un registro fijo de técnicas ya construidas por el equipo; un
  generador determinista (`challenge_generator.py`, ej. con Scapy) materializa el archivo real.
  La IA nunca inventa mecanismos nuevos ni genera archivos/binarios directamente. Detalle
  completo en `docs/pipeline_ia_retos.md`. Alcance del MVP: solo 1-2 categorías (crypto y
  network) tienen el pipeline completo; el resto usa retos estáticos.
* **Equipo de backend ahora son 2 personas (26 ago).** El trabajo se dividió por archivos para
  evitar colisiones de Git — ver `.claude/memory/reparto_tareas.md` **antes de tocar código**
  si hay más de una persona trabajando en el backend el mismo día.
* **Flujo de Git del equipo (nuevo, 26 ago):** nadie commitea directo sobre `main` — cada
  persona trabaja en su propia rama (`feature/<algo>`), pushea esa rama a GitHub, y se junta a
  `main` recién con un Pull Request cuando el trabajo está listo. Esto es clave porque el
  equipo ya divide el trabajo por archivos: si cada quien commitea directo a `main`, el primero
  que pushea "empuja" al resto a hacer `pull` antes de poder seguir, y aumenta el riesgo de
  pisarse aunque los archivos no se toquen. La rama de esta sesión: `feature/retos-ia-persona2`
  (ya pusheada a GitHub, todavía no mergeada a `main`).
* **Versión de Python para el venv del backend:** usar **Python 3.12**, no la versión más nueva
  que tenga instalada cada máquina (ej. 3.14). Motivo: `psycopg2-binary==2.9.10` (la versión
  fijada en `requirements.txt` hasta el 26 ago) no tiene wheel precompilado para Python 3.14 en
  Windows, y compilarlo desde código fuente falla porque falta `pg_config`/PostgreSQL local. El
  26 ago alguien del equipo subió `psycopg2-binary==2.9.12` a `requirements.txt`, que según el
  mensaje de ese commit agrega soporte para 3.14 — **sin confirmar todavía** con una instalación
  real en 3.14; hasta confirmarlo, seguir usando 3.12 es la opción segura y probada.

## Progreso técnico

* Repositorio Git inicializado, con historial de commits.
* `backend/venv/` creado (Python 3.12); dependencias instaladas y fijadas en
  `backend/requirements.txt` (fastapi, uvicorn, sqlalchemy, alembic, pydantic,
  pydantic-settings, psycopg2-binary, python-jose, passlib[bcrypt], python-multipart, together,
  boto3, scapy).
* `backend/.env` configurado con `DATABASE_URL` de Supabase — **conexión verificada**
  (PostgreSQL 17.6). `TOGETHER_API_KEY` y credenciales de AWS aún pendientes.
* `backend/.env.example` y `.gitignore` completos; el `.env` real nunca se sube al repositorio.
* `app/core/config.py` implementado: lee el `.env` con pydantic-settings, falla al arrancar si
  falta una variable obligatoria (probado).
* **Pipeline de generación de retos con IA implementado y probado de punta a punta (26 ago,
  Persona 2)** — las 4 piezas de esa línea del reparto están hechas:
  - `app/schemas/challenge.py`: `ChallengeSpec` de Pydantic, con `Literal` para
    category/difficulty/technique (el registro fijo) y validación de formato de flag
    (`FLAG{...}`).
  - `app/services/challenge_generator.py`: `TECHNIQUE_REGISTRY` con **ambas** técnicas del MVP
    implementadas — `generate_wep_reused_iv_pcap` (genera un `.pcap` real con Scapy, RC4 propio,
    IV reutilizado) y `generate_xor_challenge` (XOR de un solo byte). Las dos se probaron
    simulando el ataque real (recuperación de flag sin conocer la llave), no solo verificando
    que no tiran error.
  - `app/services/ai_advisor.py`: llamada a Together AI (prompting simple, sin fine-tuning
    todavía) que devuelve el JSON crudo sin validar. Probado con un cliente Together simulado
    (todavía no probado contra la API real — falta un `TOGETHER_API_KEY` real en `.env`).
  - `challenges/templates/network/template.json` y `challenges/templates/crypto/template.json`:
    llenados con ejemplos reales, validados contra `ChallengeSpec` y contra los generadores.
  - `backend/tests/unit/`: 25 tests con `unittest` de la librería estándar (sin agregar
    `pytest` a `requirements.txt` a propósito, para no tocar un archivo que el equipo ya trata
    como compartido/sensible a conflictos). Correr con:
    `venv\Scripts\python.exe -m unittest discover -s tests/unit -v`
* Resto de `backend/app/` (línea de Persona 1: `db/`, `models/user.py`, `core/security.py`,
  `api/v1/endpoints/auth.py`) sigue siendo esqueleto — ver `.claude/memory/reparto_tareas.md`.

## Pendiente (próximos pasos, en orden)

1. ~~Implementar `app/core/config.py`~~ ✅ Hecho.
2. Crear el modelo `User` (`app/models/user.py`) y su migración con Alembic. *(Persona 1)*
3. Implementar autenticación JWT (`app/core/security.py`, endpoints en `auth.py`). *(Persona 1)*
4. Crear bucket S3 + rol IAM, integrar con `boto3` — incluye conectar
   `challenge_generator.py` para subir los archivos generados a S3 en vez de dejarlos en
   `challenges/generated/` local.
5. Configurar la instancia EC2 siguiendo `docs/arquitectura_mvp.md`.
6. ~~Implementar el schema `ChallengeSpec` en `app/schemas/challenge.py`~~ ✅ Hecho (26 ago).
7. ~~Integrar Together AI en `app/services/ai_advisor.py` y `challenge_generator.py`~~ ✅ Hecho
   (26 ago) — pendiente solo probarlo contra la API real de Together cuando haya
   `TOGETHER_API_KEY`.
8. Abrir el Pull Request de `feature/retos-ia-persona2` hacia `main` cuando el equipo esté listo
   para juntar el trabajo de ambas líneas.
9. Implementar `generate_xor_challenge` como técnica de respaldo si Together AI no está
   disponible (ver diagrama "reintentar / usar reto estático" en `docs/pipeline_ia_retos.md`) —
   todavía no hay lógica de reintento ni de fallback automático, solo las funciones sueltas.

---

# Arquitectura general

Aplicación de escritorio

↓

Backend

↓

Docker

↓

Contenedores con herramientas

↓

Resolución de retos y validación de flags

---

# Principios de diseño

* Modularidad.
* Simplicidad.
* Escalabilidad.
* Bajo acoplamiento.
* Código mantenible.
* Arquitectura limpia.
* Priorizar un MVP funcional antes de agregar nuevas características.

---

# Reglas de comportamiento para el asistente

El asistente debe actuar como un arquitecto de software y desarrollador con criterio técnico.

No debe asumir que una idea es correcta solo porque fue propuesta por el equipo.

Debe mantener una postura objetiva, crítica y fundamentada.

Su función es ayudar a construir la mejor solución posible, no validar automáticamente las decisiones tomadas.

Debe:

* Identificar riesgos técnicos.
* Detectar sobreingeniería.
* Señalar inconsistencias en la arquitectura.
* Explicar ventajas y desventajas de cada propuesta.
* Justificar todas sus recomendaciones.
* Proponer alternativas cuando existan opciones mejores.

Antes de recomendar una tecnología o funcionalidad debe evaluar:

1. ¿Es técnicamente posible?
2. ¿Es realmente necesaria?
3. ¿Aporta valor al proyecto?
4. ¿Es viable dentro del tiempo disponible?
5. ¿Existe una alternativa más simple?
6. ¿Complica innecesariamente la arquitectura?

Si una idea es mala, excesivamente compleja o poco realista, debe decirlo claramente y explicar el porqué.

No debe dar la razón automáticamente.

No debe recomendar tecnologías únicamente porque son populares.

No debe incrementar la complejidad sin una justificación sólida.

Debe priorizar siempre una solución funcional, mantenible y defendible antes que una solución excesivamente ambiciosa.

---

# Contexto del equipo

Este proyecto está siendo desarrollado por estudiantes de undécimo año del CTP Don Bosco para EXPOTEC.

El tiempo y los recursos son limitados.

Las recomendaciones deben considerar el contexto educativo del proyecto.

La mejor solución no es la más compleja ni la más innovadora, sino la que pueda implementarse correctamente, mantenerse y demostrarse exitosamente durante la defensa.

---

# Prioridad del proyecto

La prioridad absoluta es construir un MVP sólido, funcional y defendible para EXPOTEC (a finales de año, octubre 2026) y durante el año se harán defensas de proyecto con los avances que se tienen

Las funcionalidades avanzadas solo deben implementarse cuando exista una necesidad técnica demostrada y no comprometan la estabilidad del sistema.

Se prioriza:

1. Funcionalidad.
2. Estabilidad.
3. Mantenibilidad.
4. Modularidad.
5. Escalabilidad.

La complejidad nunca debe ser un objetivo por sí misma.
