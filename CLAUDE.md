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
* Integración nativa "GitHub Repository" de Supabase (migraciones vía su CLI + branching) — el
  proyecto gestiona migraciones con **Alembic** apuntando directo a `DATABASE_URL`, no con el
  CLI de Supabase. Conectarla no aporta nada (busca una carpeta `supabase/migrations/` que no
  existe) y puede generar bases de datos/costos extra si se activa el branching sin querer.

---

# Estado actual del proyecto (checkpoint de sesión)

Esta sección se actualiza al final de cada sesión de trabajo para retomar el contexto completo
desde cualquier dispositivo, ya que este archivo viaja con el repositorio Git.

**Última actualización:** 11 de octubre de 2026.

## Decisiones de arquitectura tomadas

* Supabase se usa **solo como base de datos PostgreSQL**. La autenticación se implementa en
  el backend, no con el sistema de Auth nativo de Supabase. **Cambio del 7 oct:** ya no es JWT
  stateless — ver el bullet de migración de auth más abajo.
* El sandbox de retos (Docker) es **centralizado en AWS**, compartido por todos los usuarios —
  no corre localmente en la máquina de cada estudiante. Cada contenedor se limita en memoria y
  CPU (`--memory`, `--cpus` de Docker) para no afectar a otros usuarios en la misma instancia.
* Arquitectura AWS del MVP: **una sola instancia EC2** (nginx + FastAPI + Docker host juntos),
  subred pública, un Security Group como único firewall, sin NAT Gateway ni subredes privadas.
  Detalle completo en `docs/arquitectura_mvp.md`. **Reconfirmado el 7 oct** después de ver el
  alcance real de `wispr_terminal_professional` (terminal Kali por jugador vía Docker +
  node-pty/ws, lecciones, panel admin, grupos): la cantidad de archivos/funcionalidades no
  cambia el cálculo — lo que de verdad pesa en la instancia es cuántos contenedores Kali
  concurrentes corren a la vez, no cuánto código hay. Para EXPOTEC (demo, 4 personas en un solo
  dispositivo) una instancia mínima (`t3.small`/`t3.medium`) sobra. Para un piloto real de aula
  (20-30 estudiantes concurrentes) sigue siendo **una sola instancia**, solo que de un tamaño
  mayor — eso se dimensiona con datos reales de uso de RAM/CPU de un contenedor Kali cuando
  llegue el momento, no ahora. Fargate/ALB siguen descartados por lo mismo de siempre: esa
  complejidad solo se justifica en escalas de cientos de usuarios concurrentes.
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
* **Equipo de backend: 2 personas (26 ago) — el reparto por archivos ya no aplica (11 oct).**
  La Persona 1 (dueña de este repo) lleva todo el backend; la Persona 2 ahora trabaja en AWS
  (desplegar el proyecto en la nube). `.claude/memory/reparto_tareas.md` queda solo como
  registro histórico de cómo se dividió el trabajo entre el 26 ago y el 7 oct.
* **Fusión de `feature/retos-ia-persona2` a `main` (7 oct).** El pipeline de generación de
  retos con IA diseñado en `docs/pipeline_ia_retos.md` ya es código real en `main`: `ChallengeSpec`,
  `TECHNIQUE_REGISTRY` (`iv_reuse_wep`, `xor_singlebyte`), `ai_advisor.py`, las plantillas de
  `challenges/templates/` y 25 tests. Sin conflictos de código al fusionar — las dos líneas de
  trabajo nunca tocaron los mismos archivos; solo hubo que resolver a mano la documentación
  (este archivo y `.claude/memory/`). **Decisión del mismo día:** el fine-tuning con LoRA queda
  en pausa (se está resolviendo por separado); mientras tanto `ai_advisor.py` sigue con
  **prompting simple** contra el modelo base de Together AI, sin bloquear el resto del pipeline.
* Política de equipo (26 ago, documentada solo en la rama de Persona 2 hasta esta fusión):
  nadie commitea directo a `main`, cada persona trabaja en su rama `feature/<algo>` y junta con
  Pull Request. No se cumplió entre el 26 ago y el 7 oct por esto mismo — vale la pena
  re-confirmarla con el equipo ahora que ya está visible para ambos en `main`.
* Versión de Python para el venv del backend: **3.12, 3.13 o 3.14** sirven. La restricción
  anterior ("solo 3.12") era porque `psycopg2-binary` no tenía instalador precompilado para
  Windows en 3.14. **Verificado el 11 oct:** `psycopg2-binary==2.9.12` (el de
  `requirements.txt`) ya publica wheels `win_amd64` para cp312, cp313 y cp314, así que en
  Windows se instala sin compilar nada ni tener PostgreSQL local.
* **Auth con MFA migrado de `wispr_terminal_professional` a FastAPI (7 oct).** Ese proyecto
  (carpeta aparte, `/home/lonsoo/wispr_terminal_professional`, no es un repo Git) tenía un
  backend Node real y ya probado con correo real: registro/login con código de 6 dígitos,
  sesiones, bloqueo por fuerza bruta. Su contrato de API está documentado en
  `docs/BACKEND-PENDIENTE.md` de ese proyecto. Decisiones tomadas al migrar:
  - **Rutas idénticas a las del prototipo** (`/api/players/register`, `/verify`, `/resend`,
    `/login`, `/login-verify`, `/login-resend`, `/me`, `/logout`), montadas en FastAPI sin el
    prefijo `/v1`, para que el frontend ya terminado no tenga que cambiar sus llamadas — solo
    apuntar su URL base (`<meta name="wispr-api">` en `index.html`) a este backend.
  - **Sesiones revocables respaldadas en Supabase, no JWT.** El prototipo usaba un token opaco
    cuyo hash SHA-256 vive en servidor (revocable de verdad al hacer logout/bloquear una
    cuenta) — se decidió mantener ese esquema en vez del JWT stateless que ya estaba hecho en
    `security.py`, porque un JWT no se puede revocar sin una lista negra aparte. Implementado en
    `app/core/sessions.py` + tabla `sessions` nueva (antes era `lab/data/sessions.json`).
  - Lógica de negocio migrada 1:1 desde `server.js` a `app/services/auth_flow.py`: validaciones,
    mensajes de error en español (el frontend los muestra directo), rol por dominio
    institucional, bloqueo tras 5 fallos en 15 min, mensaje de error genérico para no filtrar
    qué cuentas existen. Contraseñas con **bcrypt** (ya probado) en vez del `scrypt` del
    prototipo — mismo nivel de seguridad, sin reimplementar nada.
  - Los endpoints viejos (`/api/v1/auth`, `/api/v1/users`, JWT sin MFA) se **eliminaron**, no se
    dejaron en paralelo — convivir con la ruta vieja sin MFA sería un agujero de seguridad.
  - **Fuera de alcance a propósito:** retos/progreso/ranking/grupos/terminal Kali (todo lo demás
    que ya tiene `server.js`) — esto fue solo la migración de auth. `publicPlayer()` devuelve
    `solved`/`attempts`/`submissions`/`lessonProgress` vacíos por ahora para no romper al
    frontend, que ya espera esas llaves.
  - 59 tests (35 nuevos de esta migración) pasan contra una base SQLite en memoria — no se pudo
    probar contra Supabase real porque estaba pausado. **Pendiente real: aplicar la migración
    de Alembic y probar el flujo completo con Supabase reactivado antes de dar esto por cerrado.**
  - ~~Hallazgo de seguridad: contraseña de Gmail en `wispr_terminal_professional/.env.example`~~
    **Cerrado (11 oct):** confirmado con la compañera que es una contraseña falsa/vieja que ya
    no se usa.
* **Autenticación con verificación de correo (MFA) + perfil de usuario ampliado (nuevo, 13 sep).**
  Decisión de equipo: el registro **y** el login exigen un código de verificación de 6 dígitos
  enviado al correo (doble capa: contraseña + posesión del correo). Se decidió MFA en ambos
  pasos a propósito, aceptando la fricción extra en cada login a cambio de más seguridad.
  El modelo `User` se amplía con `full_name`, `gender` y `role` (`estudiante` | `profesor` |
  `admin`); el `username` existente se reutiliza como "handle" (no se agrega un campo aparte).
  El **rol se deriva del dominio institucional** (`@est.cedesdonbosco.ed.cr` → estudiante,
  `@cedesdonbosco.ed.cr` → profesor); cualquier otro correo válido se acepta y entra como
  **estudiante** por defecto. El login sigue siendo por **correo** + contraseña (estándar
  OAuth2), no por handle.
  - **Envío de correo:** SMTP con `smtplib` (biblioteca estándar de Python, sin dependencia
    nueva), con **fallback a "modo desarrollo"** (el código se registra en consola/archivo en
    vez de fallar) para que un SMTP caído nunca bloquee el registro. Requiere variables `SMTP_*`
    nuevas en `config.py` y `.env.example`.
  - **Almacén de códigos:** en memoria (un diccionario en el proceso), suficiente para el MVP de
    **una sola instancia EC2**. Nota de escala: si algún día se corren varios workers, mover a
    una tabla en la BD (Redis está descartado). Se deja señalado para no sobre-ingeniar ahora.
  - **Aviso de entrega institucional:** el Workspace del colegio **rechaza correo externo**
    (rebote `550 5.7.1`, política institucional). Con un Gmail remitente los códigos llegan a
    dominios externos (gmail, etc.), pero para correos `@*.cedesdonbosco.ed.cr` hará falta que el
    Departamento de Sistemas ponga el remitente en lista blanca, o que den un SMTP interno.
  - **Origen:** estas funciones se prototiparon por error en un frontend aparte en Node
    (`wispr_terminal_professional`) en vez de en este backend. Ese prototipo ya validó el flujo
    completo (registro→verificación→login→verificación con correo real). Ahora se **migran a
    FastAPI**, que es donde corresponden. La migración es trabajo de la **Persona 1** y no toca
    archivos de la Persona 2.
  - **Terminal Kali/Docker:** por ahora permanece como servicio Node aparte del prototipo; su
    ubicación definitiva se decidirá más adelante (criterio: que sea funcional y no exponga
    datos). No forma parte de esta migración de auth.

## Progreso técnico

* Repositorio Git inicializado, con historial de commits.
* `backend/venv/` creado (Python 3.12–3.14, ver nota arriba); dependencias instaladas y fijadas en `backend/requirements.txt`
  (fastapi, uvicorn, sqlalchemy, alembic, pydantic, pydantic-settings, email-validator,
  psycopg2-binary, python-jose, bcrypt, python-multipart, together, boto3, scapy).
* `backend/.env` configurado con `DATABASE_URL` de Supabase — **conexión verificada**
  (PostgreSQL 17.6). `TOGETHER_API_KEY` y credenciales de AWS aún pendientes.
* `backend/.env.example` y `.gitignore` completos; el `.env` real nunca se sube al repositorio.
* `app/core/config.py` implementado: lee el `.env` con pydantic-settings, falla al arrancar si
  falta una variable obligatoria (probado).
* `app/db/session.py`, `app/db/base.py`, `app/models/user.py` implementados. Alembic
  configurado (`migrations/alembic.ini`, `env.py`, `script.py.mako`) y la primera migración
  aplicada: tabla `users` real en Supabase (id, email, username, password_hash, points,
  is_active, created_at).
* `app/core/security.py` implementado y probado (hash de contraseñas + JWT). Se usa `bcrypt`
  directamente, no `passlib` — `passlib[bcrypt]` está roto con versiones nuevas de `bcrypt`
  (bug conocido, no reintroducir `passlib` sin verificar que se haya solucionado).
* `app/schemas/user.py` implementado y probado: `UserCreate`, `UserPublic` (nunca expone
  `password_hash`), `UserUpdate`, `Token`. Requirió agregar `email-validator` a
  `requirements.txt` (Pydantic necesita ese paquete aparte para el tipo `EmailStr`).
* `backend/main.py` implementado por primera vez: crea la app FastAPI, agrega CORS (para que
  Electron pueda llamarlo), y una ruta `/` de salud.
* `tests/unit/test_security.py` agregado — las pruebas manuales de `security.py` ahora son
  automáticas con `pytest` (agregado a `requirements.txt` junto con `httpx`).
* **(Reemplazado el 7 oct)** `app/api/v1/endpoints/auth.py`/`users.py` (login simple sin MFA,
  JWT stateless) se **eliminaron** — ver el bullet de migración de auth en "Decisiones de
  arquitectura" más arriba, y el siguiente bullet.
* **Auth con MFA + sesiones revocables, migrado de `wispr_terminal_professional` (7 oct) —
  verificado contra Supabase real el mismo día.** `app/api/players.py` (rutas `/api/players/*`),
  `app/services/auth_flow.py` (registro, login, bloqueo por fuerza bruta — lógica migrada 1:1
  del prototipo Node), `app/core/sessions.py` + modelo `app/models/session.py` (sesiones
  revocables respaldadas en una tabla nueva, no JWT), `app/services/email.py` (envío por
  `smtplib` con fallback a modo desarrollo). Migración Alembic `27e315b1d2f6` **aplicada** a
  Supabase (verificado: `public.users` tiene las columnas nuevas, `public.sessions` existe).
  59 tests automáticos pasan contra SQLite en memoria (20 en `tests/unit/test_auth_flow.py` +
  4 de integración HTTP en `tests/integration/test_players_api.py` + los 35 ya existentes).
  Además se corrió **manualmente el flujo completo contra la Supabase real, con SMTP real**
  (mismas credenciales de `wispr_terminal_professional/.env` — `SMTP_USER=wispr.info@gmail.com`,
  ya copiadas a `backend/.env`): `uvicorn` corriendo de verdad (no `TestClient` en un proceso de
  un solo request — así los códigos pendientes, en memoria, sobreviven entre peticiones igual
  que en producción) → registro → **correo real recibido**, verificado con el código real →
  cuenta creada en Supabase → `/me` → login → **segundo correo real**, verificado con su código
  → segunda sesión → `logout` revoca **solo esa sesión** (confirmado: la primera, la del
  registro, seguía viva) → bloqueo tras 5 fallos probado por separado contra Supabase también.
  Usuario y sesiones de prueba borrados al terminar (`public.users`/`public.sessions` en 0 filas,
  confirmado) y el servidor de prueba detenido. **Nota:** nada de esto quedó como test
  automatizado en el repo (manda correos reales y pega contra servicios externos reales) — el
  resultado queda documentado acá, no hay script que repetirlo.
* **Frontend y backend "entrelazados" — probado con la UI real (7 oct).** Se instaló Playwright
  (`pip install playwright` + `playwright install chromium`; no hay Node/npm en este entorno, no
  hacía falta). Con `wispr_terminal_professional` servido como archivos estáticos (sin su
  `server.js`, que no hacía falta para esto) y su único cambio temporal —
  `<meta name="wispr-api" content="http://127.0.0.1:8799">`, revertido al terminar — un navegador
  headless real completó "Crear cuenta" → formulario de registro (coincide **exacto** con el
  payload que ya migramos: `name`/`handle`/`gender`/`password`/`email`) → envío → la pantalla de
  MFA ("Verificación de correo institucional", badge `ESTUDIANTE`, correo enmascarado,
  `Verificar y entrar`) apareció de verdad, con el toast de confirmación del correo real enviado.
  Captura guardada en el scratchpad de la sesión (no en el repo). Esto confirma que el frontend
  terminado puede hablar con este backend **sin que el equipo de frontend cambie una sola línea**
  — solo apuntar esa `<meta>` al backend real cuando se despliegue. `wispr_terminal_professional`
  quedó intacto (el único archivo tocado, `index.html`, se restauró con un backup).
* **Nota recurrente — Supabase se pausa solo:** plan gratuito, se pausa tras varios días sin
  actividad. Ya pasó dos veces. Si algo que antes funcionaba da
  `could not translate host name ... to address`, no es un bug de código — reactivar en
  supabase.com → proyecto → "Restore project" (1-2 min) antes de asumir que algo se rompió.
  Detalle en `.claude/memory/reparto_tareas.md`.
* **Pipeline de generación de retos con IA implementado, probado y fusionado a `main` (26 ago,
  Persona 2 — fusión el 7 oct)** — las 4 piezas de esa línea del reparto están hechas:
  - `app/schemas/challenge.py`: `ChallengeSpec` de Pydantic, con `Literal` para
    category/difficulty/technique (el registro fijo) y validación de formato de flag
    (`WISPR{...}`).
  - `app/services/challenge_generator.py`: `TECHNIQUE_REGISTRY` con **ambas** técnicas del MVP
    implementadas — `generate_wep_reused_iv_pcap` (genera un `.pcap` real con Scapy, RC4 propio,
    IV reutilizado) y `generate_xor_challenge` (XOR de un solo byte). Las dos se probaron
    simulando el ataque real (recuperación de flag sin conocer la llave), no solo verificando
    que no tiran error.
  - `app/services/ai_advisor.py`: llamada a Together AI (prompting simple, sin fine-tuning
    todavía) que devuelve el JSON crudo sin validar. Probado con un cliente Together simulado
    (todavía no probado contra la API real — falta un `TOGETHER_API_KEY` real en `.env`).
    **Decisión del 7 oct:** el fine-tuning con LoRA queda en pausa mientras se resuelve por
    separado; mientras tanto el pipeline usa prompting simple contra el modelo base, sin
    bloquear el resto.
  - `challenges/templates/network/template.json` y `challenges/templates/crypto/template.json`:
    llenados con ejemplos reales, validados contra `ChallengeSpec` y contra los generadores.
  - `backend/tests/unit/`: 25 tests con `unittest` de la librería estándar (sin agregar
    `pytest` a `requirements.txt` a propósito, para no tocar un archivo que el equipo ya trata
    como compartido/sensible a conflictos). **Actualizado 11 oct:** `pytest` ya está en
    `requirements.txt` y los tests nuevos lo necesitan (fixtures). Correr TODO desde `backend/` con
    `venv\Scripts\python.exe -m pytest` (Windows) o `venv/bin/python -m pytest` (Linux/Mac).

* **Loop jugable migrado de `wispr_terminal_professional` (11 oct) — verificado contra Supabase
  real.** Rama `feature/retos-envios-ranking`. Decisiones:
  - **Flag unificada a `WISPR{...}`** (antes `FLAG{...}` en el pipeline Python): es la que ya
    usan el frontend, los retos Wi-Fi y `ctf submit` de la terminal. Mismo regex que el prototipo.
  - Tablas nuevas (migración `dba06aee3303`): `challenges`, `submissions` (cada intento),
    `solves` (primer acierto, PK (user, reto) — impide sumar puntos dos veces aunque lleguen dos
    envíos a la vez; probado con envíos simultáneos contra Postgres real), `challenge_instances`
    (flag personal por jugador, vacía por ahora) y `lesson_progress`.
  - `flag_validator.py` (flag personal si existe, si no la del catálogo; tiempo constante),
    `scoring.py` (envíos, racha, progreso, ranking), `lessons.py`, `challenges.py` (forma
    pública sin flag/solución, sembrado) y rutas en `app/api/challenges.py` montadas en `/api`
    con el contrato exacto del frontend. El `playerId` que manda el frontend se ignora: el
    jugador sale siempre de la sesión. `/api/players/me` ya devuelve el progreso real.
  - Catálogo en `challenges/catalog/catalog.json`: los 8 retos Wi-Fi exportados tal cual del
    prototipo (con archivos fijos en `challenges/static/`, ver punto 7b) + WEP y XOR del pipeline. Se carga con `python -m app.db.seed_challenges`
    (idempotente; ya cargado en Supabase).
  - Sin terminal Kali todavía: `/challenges/active` no arranca contenedores y
    `/platform/status` informa Docker no disponible. `nextChallenge` siempre `None`.
  - En producción (`ENVIRONMENT=production`) el MFA ya no cae a modo desarrollo.
  - 87 tests pasan. Prueba manual con `uvicorn` real + Supabase: catálogo sin flags, flag XOR
    recuperada del archivo descargado, envíos, `/me`, ranking, lecciones; usuario temporal
    borrado al final (0 filas restantes).
  - **Probado con la UI real (12 oct):** frontend `wispr_terminal_professional` servido sin
    modificar ningún archivo (un servidor estático temporal reescribía el `<meta name="wispr-api">`
    solo en la respuesta) + backend real + Supabase. El usuario completó registro con correo real,
    retos, descargas, envío de flags, ranking y lecciones: todo funcionó. Cuenta de prueba y sus
    datos borrados de Supabase al terminar (quedan solo los 10 retos del catálogo).

## Pendiente (próximos pasos, en orden)

1. ~~Implementar `app/core/config.py`~~ ✅ Hecho.
2. ~~Crear el modelo `User` y su migración con Alembic~~ ✅ Hecho — tabla `users` creada en
   Supabase (migración `1b4b30f0b1aa_create_users_table.py`).
3. ~~Implementar `app/core/security.py` (hash de contraseñas + JWT)~~ ✅ Hecho y probado.
4. ~~Implementar `auth.py`, `users.py`, router de v1 y `main.py`~~ ✅ Hecho — **reemplazado el
   7 oct** por la migración de auth con MFA (siguiente punto); ya no existen esos archivos.
5. ~~Fusionar `feature/retos-ia-persona2` a `main`~~ ✅ Hecho (7 oct) — ver "Progreso técnico".
6. ~~Migración de auth con MFA por correo + perfil ampliado~~ ✅ Hecho, migración aplicada y
   **verificado contra Supabase real, con correo real** (7-8 oct) — ver "Progreso técnico".
   Queda:
   a) ~~Rotar la contraseña de Gmail de `wispr_terminal_professional/.env.example`~~ Cerrado
      (11 oct): era falsa y ya no se usa. La de `backend/.env` (`wispr.info@gmail.com`) es la real.
   b) ~~Apuntar el frontend a este backend y confirmar que el flujo real funciona con la UI~~
      ✅ Hecho (7 oct, con Playwright — ver "Progreso técnico"). Falta que el equipo decida
      **dónde vive de forma permanente** esa URL del backend (hoy el `<meta name="wispr-api">`
      de `wispr_terminal_professional/index.html` sigue vacío = mismo origen; hay que decidir
      si ese frontend termina sirviéndose junto al backend en la misma instancia EC2 o separado).
7. ~~Retos, envíos de flags, ranking y progreso de lecciones~~ ✅ Hecho y **verificado contra
   Supabase real** (11 oct) — ver "Progreso técnico". Rama `feature/retos-envios-ranking`.
7b. ~~Retos Wi-Fi jugables~~ ✅ **Solución temporal hecha (11 oct):** los 8 retos Wi-Fi usan
   archivos **fijos** (un `.pcap` + `wordlist.txt` por reto, iguales para todos los jugadores) en
   `challenges/static/`, generados UNA vez con el generador del prototipo:
   `node challenges/static/generar_wifi.js /ruta/a/wispr_terminal_professional` (determinista). El
   backend **no necesita Node**: solo sirve esos archivos. `tests/unit/test_wifi_static.py` resuelve
   los 8 con Python/Scapy (PBKDF2, MIC del handshake, PMKID — sin usar el código Node) y confirma que
   dan la flag del catálogo. Los 10 retos ya se pueden descargar y ganar.
7c. **(Futuro — solo si se justifica) Archivos por jugador en Python.** Límite real de la solución
   temporal: como todos reciben el mismo archivo, **un estudiante puede pasarle la flag a otro**.
   - **Cuándo SÍ hacerlo:** antes de usar WISPR para **evaluar** a un grupo real (nota, ranking de
     aula), o si se muestra el ranking como algo competitivo entre muchos estudiantes. Ahí copiar
     flags arruina la medición.
   - **Cuándo NO hace falta:** la demo de EXPOTEC (4 personas, un dispositivo) y las defensas de
     avance: la solución temporal alcanza y no conviene gastar tiempo ahí.
   - **Por qué Python y no seguir con Node:** el backend es Python; generar en el momento con Node
     obligaría a correr dos runtimes en el servidor y repartir la "flag correcta" entre dos
     servicios. La criptografía ya está validada en Python (el test de arriba la usa para resolver);
     falta la parte de *construir* las tramas, ~440 líneas de `pcap-wifi.js` + `pcap-challenges.js`.
     Orden: deauth → PMKID → WPA. La tabla `challenge_instances` y `flag_validator.py` ya están
     listos para esto; frontend y rutas no cambian.
   Después: conectar `nextChallenge` (reto de continuación) con `ai_advisor.py`. Terminal Kali,
   S3 + IAM y la instancia EC2 siguen después, como estaba decidido.
8. Probar `ai_advisor.py` contra la API real de Together (falta un `TOGETHER_API_KEY` real) y
   agregar la lógica de reintento/respaldo — usar `xor_singlebyte` como técnica estática si
   Together AI no responde o devuelve algo inválido (hoy esa función solo propaga el error). El
   fine-tuning con LoRA queda fuera de esto hasta que se resuelva por separado.
9. Crear bucket S3 + rol IAM, integrar con `boto3` — incluye conectar
   `challenge_generator.py` para subir los archivos generados a S3 en vez de dejarlos en
   `challenges/generated/` local.
10. Configurar la instancia EC2 siguiendo `docs/arquitectura_mvp.md`.

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
