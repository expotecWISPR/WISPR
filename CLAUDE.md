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

Los retos no se generan libremente por IA sin control. **Desde el 13 oct** (guía del
ingeniero, `docs/Guía WISPR retos variados y dificultad adaptativa.pdf`) el reparto es:

1. **Lo decide el backend (código):** la técnica (registro fijo), la dificultad (motor
   adaptativo, `app/services/difficulty.py`), los parámetros de cada nivel
   (`challenge_generator.py`) y la flag (aleatoria, con `secrets`, distinta por jugador).
2. **Lo escribe la IA (Together AI + Muse Glimmer 30B; hasta el 23 oct, Llama 3.3 70B):** solo la historia — título, descripción y
   una pista —, con un escenario elegido al azar y sin repetir los títulos que el jugador ya vio
   (`app/services/ai_advisor.py`). Si falla, se usa una plantilla.
3. **Materialización (determinista):** todo se valida con `ChallengeSpec`
   (`app/schemas/challenge.py`) y el generador del equipo construye el archivo **de ese
   jugador** (`app/services/instances.py`).

Por qué se cambió: antes la IA generaba el reto entero (narrativa + flag + técnica + dificultad)
y, con solo 2 técnicas posibles, lo único que podía variar era el texto — repetía los ejemplos.
La variedad real ahora sale del código (archivo y flag por jugador, niveles que cambian el
archivo) y la IA aporta variedad de historias. La IA **no inventa mecanismos nuevos** ni decide
nada que haga a un reto más fácil o más difícil.

Técnicas con generador (22 oct, 6): `xor_singlebyte`, `iv_reuse_wep`, `caesar_vigenere`,
`encoding_layers`, `http_plaintext_pcap` y `stego_png` — cada una con 3 niveles reales. Los retos
Wi-Fi (deauth, handshake, PMKID) siguen siendo estáticos hechos a mano.

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
* escribir la historia (título, descripción y pista) de cada reto nuevo que el motor adaptativo
  crea para un jugador. La técnica, la dificultad y la flag las decide el backend (13 oct).

La IA no reemplaza el motor de generación procedural: aporta el texto, el motor determinista
decide y materializa. Ningún archivo, contenedor o flag se genera sin pasar primero por la
validación de Pydantic. Detalle completo del flujo en `docs/pipeline_ia_retos.md`.

**Modelo y método (actualizado 23 oct):** `meta-models/Muse-Glimmer-30B` vía Together AI
(configurable con `TOGETHER_MODEL` en el `.env`), **modelo base guiado con instrucciones**
(*prompting*), sin fine-tuning. Hasta el 23 oct fue Llama 3.3 70B Instruct Turbo, que Together
retiró ese día. **LoRA se intentó y quedó trabado** (el equipo lo describe como "un bucle sin
arreglar"); no se usa. El dataset de ~500 ejemplos curados por el equipo sigue listo por si se
retoma después de EXPOTEC. Fine-tuning completo: se evaluó y se descartó por costo y GPU.

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
* Muse Glimmer 30B (`meta-models/Muse-Glimmer-30B`, desde el 23 oct; antes Llama 3.3 70B
  Instruct Turbo, retirado por Together) — modelo base guiado con instrucciones, sin
  fine-tuning. Se elige con `TOGETHER_MODEL`. Dataset curado por el equipo (~500 ejemplos)
  listo para un LoRA futuro; el intento de LoRA quedó trabado y no se usa.
* El **fine-tuning completo** (reentrenar todos los parámetros del modelo) se evaluó y se
  descartó: requiere GPUs dedicadas y días de entrenamiento, inviable con los recursos del
  equipo. LoRA es viable porque solo entrena una fracción pequeña de los parámetros y corre
  como servicio administrado.
* Usos: escribir la historia (título, descripción, pista) de cada reto nuevo — ver
  `docs/pipeline_ia_retos.md`. La recomendación y el ajuste de dificultad los hace el motor de
  reglas (`difficulty.py`), no la IA.

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
* LLM genérico — resuelto: se usa específicamente Together AI (Muse Glimmer 30B desde el 23 oct).
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

**Última actualización:** 22 de octubre de 2026.

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
* **Ramas: ya no se usan (12 oct).** La política del 26 ago (ramas `feature/<algo>` + Pull
  Request, nadie commitea directo a `main`) se dejó: el backend lo lleva una sola persona y el
  frontend vive en su propio repositorio (`WISPR-frontend`, ver pendiente 6b). Se commitea
  directo a `main`.
* **Guía del ingeniero: retos variados y dificultad adaptativa (13 oct).** PDF en `docs/`. Problema:
  la IA repetía los ~500 ejemplos en vez de crear retos nuevos. Diagnóstico confirmado en el código:
  la IA no se llamaba en ningún lado, los archivos y flags eran iguales para todos, la dificultad
  solo cambiaba los puntos y `nextChallenge` siempre era `None`. Decisiones tomadas al aplicarla:
  - **La IA solo escribe la historia; la técnica, la dificultad y la flag las decide el código**
    (ver "Generación de retos" arriba). Se borró `generate_challenge_spec_raw()`.
  - Categorías: `stego`, `reverse` y `misc` se **agregaron** al `Literal` de `ChallengeSpec` en vez
    de reclasificar ~290 retos a mano: lo que decide qué código corre es `technique`, no la categoría.
  - La instancia por jugador se crea **al pedir el archivo**, no en `POST /challenges/active` como
    decía la guía: esa ruta la atiende Node (nginx), FastAPI no la ve. La descarga sí pasa siempre
    por FastAPI (web y Node, con el token del jugador), así que los dos reciben el mismo archivo.
  - El nivel por categoría **no se guarda en una tabla**: se calcula del historial
    (`submissions`/`solves`), así nunca se desincroniza. El uso de pistas todavía no cuenta (el
    frontend no le avisa al backend al abrir una).
  - WEP: las IPs del ARP conocido quedan **fijas** (son el texto conocido documentado en el
    objetivo); IV, MACs y llave se sortean en cada archivo. Randomizar las IPs obligaría a mostrar
    un objetivo distinto por jugador.
  - En esta PC, Norton inspecciona HTTPS y Python no confía en su certificado: se agregó
    `truststore` (usa los certificados de Windows/Linux) solo para el cliente de Together.
* Versión de Python para el venv del backend: **3.12, 3.13 o 3.14** sirven, en Windows y Linux.
  **Verificado el 12 oct con `uv pip compile --only-binary :all:`** (simula la instalación en cada
  plataforma sin compilar nada) para las 6 combinaciones. Corrección: el 11 oct se dijo lo mismo
  mirando solo `psycopg2-binary`, pero `pydantic==2.10.4` (su `pydantic-core`) **no tenía
  instalador para 3.14** y la instalación habría fallado; se resolvió subiendo a `pydantic==2.13.5`.
  Si se cambia cualquier versión de `requirements.txt`, repetir esa verificación.
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
    datos). No forma parte de esta migración de auth. **Decidido el 12 oct:** se queda en Node, en
    "modo conectado" con FastAPI (ver "Progreso técnico").

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

* **Pruebas de seguridad para el informe + corrección de vulnerabilidades (12 oct).** Resultados
  en `docs/pruebas_seguridad.md` (y el `.docx` del informe en `docs/`). Corregido en el backend:
  error 500 con contraseña > 72 bytes (registro y login) y con correo > 255; nombre con HTML ahora
  se rechaza (lista de caracteres permitidos); correo con regex estricto; contraseña mínima 8
  (antes 4); login con tiempo constante (no revela qué usuarios existen); límite de peticiones en
  memoria (`app/core/rate_limit.py`: por IP generoso por el NAT del colegio, 3 registros/10 min por
  correo, 30 envíos/min por jugador); cabeceras de seguridad; CORS configurable (`CORS_ORIGINS`);
  `/docs` oculto en producción. Dependencias: se quitó `python-jose` (y el código JWT muerto) y
  `python-multipart` (sin uso); se actualizaron fastapi/starlette/uvicorn/together/pydantic/scapy/
  pytest → `pip-audit` pasó de **36 vulnerabilidades a 0** (auditando un venv limpio). Para el
  prototipo: parches en `docs/parches/` (XSS en `studentScoreChart`, `/api/kali/diagnose` filtraba
  versiones, `nodemailer` 10.0.11) — **aplicados el 12 oct** con autorización, respaldo de los
  originales en `/home/lonsoo/wispr_terminal_professional_respaldo_2026-10-12/`. Nota: el
  `node_modules/node-pty` del prototipo solo trae binarios de Windows/Mac (no arranca en Linux sin
  reinstalarlo). 120 tests.

* **Terminal Kali conectada a FastAPI — "opción A" (12 oct).** Problema: el frontend solo puede
  hablar con un servidor; con FastAPI no había terminal, y con Node la terminal usaba sus propias
  cuentas/flags (`lab/data/*.json`), sin ver Supabase. Decisión: **nginx reparte por ruta** en la
  misma instancia — `/ws/terminal`, `/api/kali/*`, `/api/challenges/active` y `/api/platform/status`
  → Node (`127.0.0.1:8787`, también sirve el frontend); todo el resto de `/api/` → FastAPI
  (`127.0.0.1:8000`). Config en `deploy/nginx/wispr.conf`. Se descartó pasar la terminal a Python
  (Docker + pty + WebSocket en FastAPI) por riesgo a 2 semanas y media de EXPOTEC.
  - Node en **modo conectado** (`WISPR_BACKEND_URL`): valida cada token con `GET /api/players/me`
    (FastAPI sigue siendo la única fuente de verdad de sesiones; si no responde, Node da 503 = falla
    cerrado), baja de FastAPI el catálogo y los archivos del reto al workspace (mismos archivos que la
    web → la flag coincide), reenvía cada `ctf submit` a `POST /api/submissions` con el token del
    jugador y `source: "terminal"`, y cierra una terminal abierta si la sesión deja de valer (revisa
    cada 60 s). Sin la variable, el prototipo funciona solo como antes.
  - Backend: `POST /api/submissions` acepta `source: "terminal"` (solo etiqueta; no cambia puntos).
    121 tests.
  - Parche en `docs/parches/terminal-modo-conectado.patch` (**aplicado** con respaldo en
    `/home/lonsoo/wispr_terminal_professional_respaldo_2026-10-12_conexion/`). Pasos de despliegue
    en `docs/arquitectura_mvp.md` → CONFIG AWS, punto 8 (Docker, Node 22, `node-pty` se compila en
    Linux, memoria por contenedor, `WISPR_PUBLIC_HOSTS`).
  - Probado en Linux con Docker **simulado** y `node-pty` compilado: 30 comprobaciones de punta a
    punta + UI real en Chromium (registro → Abrir Kali → `ctf submit` → 120 pts) + FastAPI caído +
    modo de siempre sin cambios. **Falta probarlo con Docker real.**

* **Retos variados + dificultad adaptativa + IA para historias (13 oct) — fases 1 a 5 de la guía.**
  Verificado contra Supabase real (migración `4c7e2a91d0b5` aplicada, seed corrido) con el guion de
  demo de la guía. 164 tests.
  - **Fase 2, niveles reales** (`challenge_generator.py`, tablas `XOR_LEVELS`/`WEP_LEVELS`): XOR
    easy = llave de 1 byte; medium = 2-4 bytes (la fuerza bruta de 256 ya no sirve, se usa el texto
    conocido `WISPR{`); hard = 5-6 bytes y en base64. WEP easy = 2 tramas; medium = el par entre
    20-50 tramas de ruido; hard = 200-400 tramas, el ARP lo manda el AP y va segundo (el método de
    medium da basura). Textos técnicos por nivel en `technique_info.py` (los escribe el equipo).
    Tests: cada nivel se resuelve como lo haría el estudiante y el método del nivel anterior falla.
  - **Fase 3, archivo y flag por jugador** (`instances.py`, columna `challenge_instances.artifact`):
    flag `WISPR{xor_<8 hex>}`; la flag de la plantilla (pública en el repo) ya no se acepta. El seed
    ya **no genera archivos** (se acabó el aviso de 7d para XOR/WEP).
  - **Fase 4, dificultad adaptativa** (`difficulty.py`): 1.º-2.º intento → sube; 3-6 intentos → se
    mantiene; 6+ fallos → baja; en los extremos se queda. `nextChallenge` ya no es `None`: en XOR/WEP
    se crea un reto nuevo para el jugador (`challenge_factory.py`, columna `challenges.owner_id`, solo
    lo ve su dueño); en Wi-Fi se recomienda uno del catálogo. `/api/players/me` trae `levels`.
  - **Fase 5, IA** (`ai_advisor.py`): Together devuelve `title`/`description`/`hint`, validados con
    `ChallengeNarrative` (sin llaves, largos, sin repetir títulos). Respaldo a plantilla si falla,
    tarda >12 s, no hay key o pasa de 20 llamadas/hora por jugador — el jugador nunca ve un error.
    El reto queda marcado `generator: "ai"` o `"template"`.
  - **Fase 1, dataset** (`challenges/dataset/`): original + limpio, con
    `python -m app.services.dataset_cleaner` (FLAG→WISPR, `technique`/`technique_notes`, lote manual
    completo + 117 del lote de IA que pasan el criterio de la guía, sin flags ni títulos repetidos).
    Valida con `DatasetChallenge`.
  - **Pedir un reto eligiendo parámetros** (plan original del pipeline: "el usuario elige categoría
    + dificultad de opciones fijas"). `POST /api/challenges/generate` con técnica, dificultad
    (Foundation/Medium/Hard) y escenario (de la lista o texto corto validado, que solo afecta la
    historia); `GET /api/challenges/options` da las opciones. **Estudiante:** reto de práctica solo
    para él y **sin puntos** (si diera puntos, se podría farmear el ranking pidiendo retos fáciles);
    máx. 5 sin resolver. **Profesor/admin:** reto para **todos** los estudiantes, con puntos, cada
    uno con su archivo y su flag (los grupos siguen solo en el prototipo Node; cuando se migren, se
    podrá publicar para un grupo). La flag **no** se personaliza: quien la elige ya sabe la
    respuesta. Formulario en `app.js` (pestaña Retos del estudiante, inicio de profesor y admin),
    sobre el rediseño sin commit. Límite: 6 pedidos cada 10 min por persona.
  - Frontend (`WISPR-frontend/server.js`, 2 líneas): Node pide el catálogo con el token del jugador
    (para ver sus retos generados) y `ctf show` dice "única para tu cuenta" solo si lo es.
  - ~~La `TOGETHER_API_KEY` de esta PC es inválida~~ **Resuelto el mismo 13 oct:** se puso una key
    real y las historias de la IA funcionan (~2.5 s por historia).

* **Víspera de la defensa (14 oct).** Login con MFA revisado de punta a punta (registro → código →
  logout → login → código, pasando por Node como el navegador): funciona; el SMTP de Gmail acepta las
  credenciales. Causa más probable del "código que no sirve": todos los correos tenían el **mismo
  asunto**, Gmail los juntaba en una conversación y se copiaba un código viejo (cada login nuevo
  invalida el anterior). **Arreglo:** el código va en el asunto (`WISPR: tu código es 123456`,
  `app/services/email.py`). Otra causa posible: reiniciar FastAPI con un código pendiente (viven en
  memoria). Cuentas de prueba creadas **a mano** en Supabase (no hay flujo para asignar rol):
  `@profe_wispr` (profesor) y `@admin_wispr` (admin), con correos `alonsolopezarias.03+profe@` /
  `+admin@gmail.com` (Gmail ignora lo que va tras el `+`, llegan al correo del dueño del repo).
  - **Hallazgo:** los paneles de admin y profesor del frontend llaman a **17 rutas que FastAPI no
    tiene** (solo existen en el prototipo Node): `/api/admin/players` (listar, eliminar, `bulk`,
    `reset-password`, `lock`), `/api/admin/groups`, `/api/groups/*` (crear, `mine`, `members`,
    `tasks`, `tasks/toggle`, `student`, `available-students`) y `/api/players/change-password`. En
    modo conectado Node las reenvía a FastAPI → 404; la UI muestra "No se pudo cargar la lista de
    cuentas" / "No se pudieron cargar tus grupos". Sí funcionan: login de ambos roles, "Crear un reto
    con IA" del profesor y Rankings. **Decisión:** para la defensa (plan B) no se muestran esas
    partes; se portan a FastAPI después (pendiente 7f).

* **Paneles de admin y profesor en FastAPI — pendiente 7f (20 oct).** Las 17 rutas que daban 404
  ya existen, con el contrato exacto del prototipo: `app/api/admin.py` (`/api/admin/players`,
  `DELETE`, `bulk`, `reset-password`, `lock`, `/api/admin/groups`), `app/api/groups.py`
  (`/api/groups/*`) y `POST /api/players/change-password`. Lógica en `app/services/admin.py` y
  `app/services/groups.py`. Migración `8f1d3c6a2b47` **aplicada a Supabase** (`alembic check` sin
  diferencias): tablas `groups`, `group_members` (PK grupo+estudiante), `group_tasks` y columna
  `users.lock_reason`. Decisiones:
  - El admin/profesor sale de la **sesión**; el `playerId` del frontend se ignora (el prototipo
    confiaba en él: cualquiera con el id de un admin actuaba como admin).
  - Contraseña nueva: mismas reglas del registro (mín. 8), vía `auth_flow.password_error`. Al
    cambiarla se cierran las **otras** sesiones del jugador; la del dispositivo actual sigue.
  - Bloquear cierra las sesiones; la terminal la cierra Node solo (revisa cada 60 s).
  - Borrar una cuenta: la base limpia en cascada sesiones, envíos, aciertos, lecciones, retos
    propios y membresías. Los grupos de un profesor borrado se conservan sin dueño
    ("(profesor eliminado)"). Se borran también sus archivos en `challenges/generated/instances/<id>`.
  - Sin historial `security` por cuenta (el frontend no lo muestra): se devuelve `[]`.
  - Una tarea solo puede ligarse a un reto que vean todos (`owner_id` NULL).
  - CORS ahora permite `DELETE`.
  - 189 tests (16 nuevos, con llaves foráneas activadas en SQLite para probar las cascadas). Prueba
    manual contra Supabase real pasando por Node: listar cuentas, 403 al profesor, crear grupo,
    agregar estudiante, detalle, tarea, borrar grupo; datos de prueba borrados. Borrar, bloquear y
    resetear cuentas **solo se probó en los tests** (no se tocaron cuentas reales).
* **Pistas que cuestan puntos — pendiente 7e(a) (20 oct).** Hallazgo: las pistas NO estaban
  bloqueadas de verdad — su texto viajaba al navegador y a `/workspace/active.json` de la terminal;
  "Mostrar" solo las ocultaba. Ahora:
  - `public_challenge` manda las pistas cerradas como `""` (más `unlockedHints` y `hintCost`). El
    texto se pide con `POST /api/challenges/{id}/hints/{n}` y queda en la tabla nueva
    `hint_unlocks` (migración `b3e9a7d41c20`, **aplicada**). Lógica en `app/services/hints.py`.
  - Cada pista abierta **antes** de resolver resta el **10 %** de los puntos del reto
    (`HINT_PENALTY_RATE`, ej. 200 pts con 2 pistas → 160). Después de resolver: gratis. Ranking,
    `/me` y grupos usan los puntos ya descontados (salen de `solves.points`).
  - Dificultad adaptativa: cada pista antes de resolver cuenta como un intento más.
  - Web (`WISPR-frontend/app.js`): "Mostrar (−N pts)" con confirmación; `app.hints` se sincroniza
    desde `/me`. Terminal: `ctf hint` pide confirmación y pide la pista por un puente de archivos
    (`hint-requests.ndjson` → Node → FastAPI → `hint-results.ndjson`), igual que `ctf submit`.
    Sin FastAPI (prototipo Node solo) todo sigue como antes. Imagen de Kali reconstruida.
  - 195 tests (6 nuevos). Probado de punta a punta con **Docker real**: un jugador temporal abrió
    Kali por WebSocket, `active.json` sin textos, `ctf hint` cobró 20 pts y quedó anotado en
    Supabase. Jugador, contenedores y workspace de prueba borrados.
* **Teoría · Módulo 2 «Seguridad Wi-Fi» (20 oct) — solo frontend (`WISPR-frontend`).** 5 temas
  (WEP, WPA y WPA2, WPA3, Cifrado, Autenticación) con Aprender → Practicar → Quiz + misión
  «Operación: Red Segura» (insignia «Guardián Wi-Fi»), sobre el mismo motor de lecciones de los
  módulos 1, 3 y 5 (`moduleMissions[2]`, motor `steps-mission`). Componentes nuevos: `m2-flow`,
  `m2-cipher`, práctica `m2-decisions`. El backend **no cambió**: el progreso viaja por
  `POST /api/progress` como el resto. Recorrido completo probado en Chromium (Playwright) con un
  estudiante temporal: todas las actividades, feedback, XP guardado en Supabase, sin XP duplicado y
  sin desborde a 390 px. Estudiante borrado al terminar.
* **Catálogo de la IA ampliado + la práctica suma puntos (22 oct).**
  - **4 técnicas nuevas** (registro fijo `TechniqueId` en `app/schemas/challenge.py`, generadores en
    `challenge_generator.py`, textos en `technique_info.py`, plantillas de respaldo en `ai_advisor.py`):
    | Técnica | easy | medium | hard |
    |---|---|---|---|
    | `caesar_vigenere` | ROT13 | César (desplazamiento ≠ 13) | Vigenère, llave de 3-5 letras |
    | `encoding_layers` | base64 | 2 capas (base64/hex/base32) | 3-4 capas, las tres, sin repetir seguidas |
    | `http_plaintext_pcap` | POST con la flag en JSON | entre ruido, formulario con %7B | base64 partido en 2 segmentos TCP + señuelos |
    | `stego_png` | metadato tEXt | base64 tras el IEND (metadato señuelo) | LSB del canal rojo (trailer señuelo) |
    Igual que XOR/WEP: archivo y flag por jugador, el método del nivel anterior falla en el siguiente.
    Un reto Foundation de cada una en el catálogo (`crypto-cesar-01`, `misc-enc-01`,
    `network-http-01`, `stego-png-01`; 14 retos en total). Kali: capa nueva en `kali/Dockerfile` con
    `exiftool`, `binwalk` y `python3-pil` (imagen reconstruida en la PC Windows).
  - **Los retos que pide el estudiante suman puntos con rendimiento decreciente** por técnica +
    nivel: 100 % → 50 % → 25 % → 0 (`challenge_factory.PRACTICE_DECAY`). Cuentan también los pedidos
    sin resolver (pedir varios de golpe no los cobra todos al 100 %). Nueva columna
    `challenges.purpose` (`practice`/`adaptive`/`class`; NULL = catálogo), migración `d7a4f19c3e58`
    **aplicada** con relleno de los retos existentes: antes "práctica" = "0 puntos", ya no sirve.
    `GET /api/challenges/options` con sesión de estudiante trae `practicePoints` y el formulario de la
    web muestra cuánto valdrá el reto antes de pedirlo.
  - 236 tests (41 nuevos). **Probado dentro de Kali real**: los 12 archivos (4 técnicas × 3 niveles)
    resueltos con los comandos exactos de las pistas (`tr`, `base64`/`base32`/`xxd`, `tshark`,
    `exiftool`, `strings`, PIL). Esa prueba encontró que en tshark 4.6 `http.file_data` sale en hex:
    las pistas de HTTP usan `json.value.string` y `urlencoded-form.value`.
* **Cronómetro por reto + bonos y penalizaciones (22 oct).** Toda la regla en
  `app/services/bonus.py` (la usan web, terminal y pistas). Sobre los puntos del reto:
  pista −15 % c/u (antes −10 %), intento fallido −5 % c/u (máx −25 %), resolver en < 10 min +15 %,
  racha limpia +5 % por cada reto **limpio** (sin pistas ni fallos) que ya se lleva seguido (máx
  +25 %; el 1.º limpio aún no tiene bono, el 2.º +5 %…). Un acierto no limpio corta la racha; los
  retos de 0 pts no la suman ni la cortan. Total nunca < 0.
  - El cronómetro lo guarda el **servidor**: `POST /api/challenges/{id}/start` la primera vez que
    se abre el reto (tabla `challenge_timers`); sin esa hora no hay bono de velocidad.
    `GET /api/challenges` trae `scoring` (reglas), `serverNow` y `startedAt` por reto; `/me` trae
    `cleanStreak` y `timers`. `solves.clean` + `solves.breakdown` (desglose guardado). Migración
    `e2b8c6d05a71` **aplicada**.
  - Frontend: tarjeta «⏱ puntos en juego» en el detalle del reto (anillo que se vacía en los 10
    min: verde → naranja en los últimos 2 → gris; marcador en vivo con signo + color; «Si lo
    resuelves ahora: N pts») y resultado con desglose al resolver; versión compacta en la terminal.
    Se actualiza cada segundo sin `render()` (no borra lo que se escribe en la flag). `ctf submit`
    muestra el desglose en una línea. **Versión final (pedido del usuario, 22 oct):** en el detalle
    del reto solo queda el anillo con el tiempo, sin tarjeta ni desglose, a la derecha del
    encabezado (debajo en pantallas angostas); al resolver queda verde con el tiempo final.
  - **Arreglo encontrado al probarlo:** las respuestas lentas del servidor (1-3 s con Supabase:
    abrir pista, arrancar cronómetro, enviar flag) hacían `render()` y **borraban la flag que el
    jugador estaba escribiendo** (lo de la pista ya pasaba antes). Ahora la flag se guarda como
    borrador por reto (`flagDrafts`), `render()` devuelve foco y cursor, y arrancar el cronómetro ya
    no redibuja la página.
  - La «racha» del ranking sigue siendo la de envíos correctos seguidos (no la racha limpia).
  - 243 tests. Probado en Chromium con todos los estados (activo, últimos minutos, vencido,
    resuelto, celular, terminal) y `ctf submit` en Kali real.
* **Recorrido de bienvenida con Wisp (22 oct).** La primera vez que un **estudiante** entra, Wisp
  (la mascota, `img/mascot.png`) lo guía en 8 pasos: bienvenida → anillo de avance → Retos → Teoría
  → Terminal → Ranking → reglas de puntos (lo que se quitó de la tarjeta del cronómetro) → su
  progreso, con «Ir a mi primer reto» (el primer Foundation sin resolver). Oscurece la página y
  deja iluminada la parte de la que habla; en el celular abre la hamburguesa para iluminar las
  pestañas. Atrás/Siguiente/Saltar, flechas y Esc, foco atrapado en la burbuja, sin animación si
  el usuario la tiene desactivada. Se repite desde Progreso («Ver el recorrido de Wisp»).
  - Se guarda en el servidor para que no se repita en otro equipo ni en Electron: columna
    `users.tour_seen_at` (migración `f4c1a8e93b26`, **aplicada**), `tourSeen` en `/me` y
    `POST /api/players/tour`. Las cuentas que ya existían lo verán una vez. Profesor y admin no
    lo ven. Sin FastAPI (prototipo Node solo) no aparece.
  - 244 tests. Probado en Chromium (escritorio y 390 px): aparece una sola vez, no vuelve al
    entrar de nuevo, Esc lo cierra, sin desborde ni errores.
* **Migración del modelo de la IA (23 oct).** Together retiró
  `meta-llama/Llama-3.3-70B-Instruct-Turbo` el 23 oct (aviso por correo a
  expociber202510@gmail.com). Ahora: `meta-models/Muse-Glimmer-30B`, la alternativa que
  recomendó Together, más barata ($0.35 entrada / $1.50 salida por millón de tokens).
  - El modelo se elige con `TOGETHER_MODEL` en el `.env` (`app/core/config.py`); por defecto el
    nuevo. Si Together vuelve a retirar uno, se cambia sin tocar código.
  - **Muse Glimmer "piensa" por dentro** y esos tokens cuentan en `max_tokens`: con los 400 de
    antes devolvía el texto vacío y todo caía a la plantilla. Arreglo en `request_narrative`:
    `extra_body={"reasoning_effort": "low"}` y `max_tokens=800`. Si se cambia a un modelo que no
    razona y Together rechaza ese parámetro, quitarlo.
  - Probado con la API real: 12/12 historias válidas (6 técnicas × 2 niveles), 3.5 s de
    promedio, 4.4 s de máximo (límite 12 s). Un reto pedido por la API salió con
    `generator: "ai"`. 244 tests.
  - **Hallazgo:** la `TOGETHER_API_KEY` del `.env` de la PC Windows era un texto de relleno de
    9 caracteres: desde el 20 oct **todas** las historias en esa PC salieron de plantilla sin
    que nadie lo notara (el respaldo no avisa). Se puso una key nueva de la cuenta del proyecto.
    Para comprobarlo en otra máquina: pedir un reto y ver que `generator` sea `"ai"`.
  - En la cuenta de Together existen dos modelos propios
    `expociber20251_08dc/Llama-3.3-70B-Instruct-Reference-…` (probablemente los intentos de
    LoRA). No se usan.
* **Máximo 15 retos por resolver (23 oct).** Pedido del usuario para que la pestaña Retos no se
  sature. Cuenta **todo** lo que el estudiante ve sin resolver, catálogo incluido (14 retos): al
  empezar puede pedir 1, y cada reto que resuelve libera un espacio. `MAX_PENDING = 15` y
  `pending_count()` en `challenge_factory.py` (reemplaza el máximo de 5 de práctica). Si al
  resolver ya tiene 15, el motor adaptativo **no crea** un reto: recomienda uno de los que ya
  tiene (`difficulty.next_challenge`). Los retos que publica un profesor no se frenan (tarea de
  clase). `GET /api/challenges/options` trae `pending` y `maxPending`.
  - Web: la pestaña Retos se divide en «Por resolver · N de 15» y «Resueltos» (cerrada por
    defecto, botón «Ver resueltos»); el formulario dice cuántos espacios quedan y se deshabilita
    con la lista llena. 245 tests; probado en Chromium (escritorio y 390 px).
* **Conexión a Supabase por IPv4 (20 oct).** En la PC Windows el backend daba
  `could not translate host name db.<ref>.supabase.co`: **no era la pausa**. Esa dirección solo
  tiene IPv6 y la red de esa PC no tiene IPv6 de internet. Arreglo: `DATABASE_URL` por el
  **Session Pooler** (`aws-0-ca-central-1.pooler.supabase.com:5432`, usuario `postgres.<ref>`).
  Para distinguirlo: `nslookup db.<ref>.supabase.co` responde solo una IP `2600:…` → es esto.

## ▶ RETOMAR AQUÍ (cierre de la sesión del 22 oct)

**Resumen del 22 oct (flujo completo y cómo funciona cada cosa): `docs/SESION-22-OCT.md`.** Todo
lo del 22 oct quedó con push en `main` de los dos repos.

Todo lo del 20 oct quedó con **push en `main`** de los dos repos (`WISPR` y `WISPR-frontend`).
EXPOTEC es a finales de octubre: quedan ~10 días. Orden acordado para seguir:

1. ~~App de escritorio con Electron~~ ✅ **Hecho (22 oct)** — `electron/` (Electron 44.7.0, ver
   `electron/README.md`). Ventana segura que abre la URL del servidor (`WISPR_URL`, por defecto
   `http://127.0.0.1:8787`): `contextIsolation` + `sandbox`, sin `nodeIntegration`, solo navega
   dentro de WISPR (lo externo va al navegador del sistema), permisos negados, una sola instancia y
   pantalla propia de «sin conexión» con «Reintentar». Se borró `ipcHandlers.js` (no hace falta
   IPC). Probado con Playwright por CDP: sin servidor → pantalla offline; con servidor → carga
   WISPR, la página no ve `require`/`process`, un enlace externo no se abre dentro. **Falta:**
   probar la terminal Kali dentro de la app (debería funcionar igual: mismo origen que el
   navegador) y, si se quiere, un instalador `.exe` (`electron-builder`). Ojo: en el entorno de
   Claude Code dentro de VS Code está definida `ELECTRON_RUN_AS_NODE=1` → hay que quitarla para
   lanzar Electron desde ahí.
2. **Despliegue en AWS (Persona 2)** — avisarle: (a) probablemente la EC2 tampoco tiene IPv6 →
   usar el Session Pooler de Supabase (ver "Conexión a Supabase por IPv4"); (b) `alembic upgrade
   head` (hay 5 migraciones nuevas: `8f1d3c6a2b47`, `b3e9a7d41c20`, `d7a4f19c3e58`, `e2b8c6d05a71`,
   `f4c1a8e93b26`) y
   `python -m app.db.seed_challenges` (14 retos); (c) construir la imagen de Kali
   **desde cero** (ver 7d); (d) arrancar Node desde una consola real o como servicio (en Windows,
   Node sin consola se cae con `AttachConsole failed` al cerrar una terminal — no afecta a Linux).
3. **Ensayo completo de la demo** en la máquina final: registro → retos → terminal (`ctf hint`,
   `ctf submit`) → profesor (grupos, tareas) → admin (cuentas, bloqueo, reset) → teoría.
4. **Alinear lo que dice este archivo con lo que hay de verdad** (para la defensa, que no pregunten
   algo que no existe):
   | Dice el proyecto | Realidad (20 oct) |
   |---|---|
   | Llama 3.3 ajustado con LoRA | ✅ Corregido (23 oct): Muse Glimmer 30B base + prompting; LoRA trabado, no se usa |
   | Pandas / scikit-learn | Dificultad adaptativa por reglas (`difficulty.py`); sin Pandas |
   | seccomp / AppArmor | Perfiles **por defecto** de Docker + `--cap-drop ALL`, `no-new-privileges`, `--read-only`, límites de memoria/CPU/procesos, red interna |
   | Docker Compose | `docker-compose.yml` vacío; los contenedores los crea Node |
   | CloudWatch | Sin configurar (parte del despliegue) |
5. **Teoría: Módulos 4 (Ataques a Wi-Fi) y 6 (Análisis) los escribe el equipo.** El asistente NO
   puede generar ese contenido (un filtro de seguridad cortó los intentos del 20 oct; no reintentar
   reformulando). Sí puede revisar el código cuando el equipo lo escriba y probarlo en el navegador.
   Guía del formato: `WISPR-frontend/docs/MODULOS-TEORIA.md`. Mientras tanto se ven como texto plano.
6. Después de EXPOTEC: 7e(b) mostrar en la UI el motivo del nivel; reto de profesor para un grupo
   (7f); S3 (9); archivos Wi-Fi por jugador (7c); Pandas (7e c); LoRA (8).

**Cómo arrancar en local (PC Windows):** `backend\.env` ya existe en esa PC (no viaja con Git).
Terminal 1: `cd backend` → `venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`.
Terminal 2: `cd ..\WISPR-frontend` → `node server.js`. Abrir http://127.0.0.1:8787. Docker Desktop
abierto para la terminal Kali. Cuentas de prueba: `admin_wispr` y `profe_wispr` (el 20 oct se
les emitieron contraseñas temporales que obligan a cambiarlas al entrar; nunca se guardan en el
repo. Si nadie las recuerda: emitir otra con `app.services.admin.reset_password`). Los códigos MFA
del profesor llegan a `expociber202510@gmail.com`.

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
      ✅ Hecho (7 oct, con Playwright — ver "Progreso técnico"). **Resuelto el 12 oct:** el
      frontend se sirve desde la misma instancia, detrás del mismo nginx (lo sirve Node), así que el
      `<meta name="wispr-api">` se queda vacío (= mismo origen). **Resuelto el 12 oct:** el código
      de `wispr_terminal_professional` (frontend + servidor Node de la terminal Kali, ya con los
      parches de `docs/parches/` aplicados) vive ahora en su **propio repositorio, `WISPR-frontend`**
      (separado de este, no dentro). Para correrlo en local: su `.env` con
      `WISPR_BACKEND_URL=http://127.0.0.1:<puerto de FastAPI>`, `npm ci` y `node server.js` (8787).
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
   - **Por qué Python y no seguir con Node:** el backend es Python; Node ya corre en el servidor
     por la terminal (12 oct), pero generar ahí los archivos obligaría a repartir la "flag
     correcta" entre dos servicios (Node la crearía y FastAPI la valida). La criptografía ya está validada en Python (el test de arriba la usa para resolver);
     falta la parte de *construir* las tramas, ~440 líneas de `pcap-wifi.js` + `pcap-challenges.js`.
     Orden: deauth → PMKID → WPA. La tabla `challenge_instances` y `flag_validator.py` ya están
     listos para esto; frontend y rutas no cambian.
   **Actualizado 13 oct:** XOR y WEP ya son por jugador (`instances.py`); solo faltan los 8 Wi-Fi.
   Al portarlos, agregarlos a `technique_info.TECHNIQUES` y `TECHNIQUE_REGISTRY` y pasan solos a
   ser por jugador y a tener retos generados por el motor adaptativo.
   ~~Después: conectar `nextChallenge` con `ai_advisor.py`~~ ✅ Hecho (13 oct).
7d. ~~Conectar la terminal Kali (Node) con FastAPI~~ ✅ Hecho (12 oct) — ver "Progreso técnico".
   Falta: probarlo con **Docker real** (computadora con Docker Desktop o la EC2) y un ensayo completo
   de la demo en esa máquina.
   - ⚠️ **Node solo construye la imagen de Kali si NO existe** (20 oct). Si ya hay una vieja, la
     sigue usando aunque `kali/` haya cambiado. Pasó en la PC Windows: imagen de 5 semanas sin
     `/etc/wispr.bashrc` (todo el texto en blanco) y con un `ctf` viejo sin `hint`. Tras cambiar
     `kali/`: `docker build --tag wispr-ctf-kali:local --file kali/Dockerfile .` desde
     `WISPR-frontend` (~25 min la primera vez) y `docker rm -f` de los contenedores `wispr-kali-*`
     (Node los vuelve a crear). Se agregaron también colores de `ls`/`grep` a `kali/wispr.bashrc`.
   - ⚠️ **En cada computadora nueva (y en la EC2), correr el seed antes de abrir la terminal:**
     `python -m app.db.seed_challenges` desde `backend/`. Los archivos de los retos del pipeline
     (`network-wep-01.pcap`, `crypto-xor-01.bin`) se generan en `challenges/generated/`, que está
     en `.gitignore` y **no viaja con el repo**. Sin ellos, FastAPI responde 404 al pedir el
     archivo, Node aborta al preparar el workspace **antes** de crear la red y los contenedores, y
     el diagnóstico de Kali muestra "network … not found" / "No such container" — parece un fallo
     de Docker pero no lo es (pasó el 12 oct en la PC Windows). El seed es idempotente y las flags
     salen del catálogo, así que correrlo de nuevo no cambia nada.
     **Actualizado 13 oct:** el seed ya no genera archivos (XOR/WEP se generan por jugador al
     pedirlos), así que este problema ya no aplica. El seed sigue haciendo falta para cargar o
     actualizar el catálogo en una base nueva.
7e. **Análisis de desempeño + dificultad adaptativa (Pandas / scikit-learn).** Es **requisito del
   proyecto** (sección "Objetivo": analizar el desempeño y adaptar la dificultad) — no se descarta
   ni se pospone indefinidamente. Los datos ya se guardan: cada envío con hora, acierto y origen
   web/terminal (`submissions`), primer acierto y puntos (`solves`), intentos y progreso de
   lecciones (`lesson_progress`).
   **Actualizado 13 oct:** la dificultad adaptativa ya funciona con reglas (`difficulty.py`, ver
   "Progreso técnico"). Falta: ~~(a) que el frontend avise al backend cuando el jugador abre una
   pista~~ ✅ Hecho (20 oct, pistas con costo — ver "Progreso técnico"); (b) mostrar en la UI el motivo del nivel (`reason` en
   `nextChallenge`, `levels` en `/me`); (c) Pandas/scikit-learn cuando haya datos reales de uso.
7f. ~~Paneles de admin y profesor en FastAPI~~ ✅ Hecho (20 oct) — ver "Progreso técnico". Falta:
   probarlo con la UI real (admin y profesor) y, si se quiere, que `POST /api/challenges/generate`
   publique un reto para **un grupo** en vez de para todos los estudiantes.
8. ~~Respaldo de `ai_advisor.py` si Together falla~~ ✅ Hecho (13 oct, plantillas). **Falta:** una
   `TOGETHER_API_KEY` válida en `backend/.env` y ver historias reales de la IA. El fine-tuning con
   LoRA queda fuera de esto; si se retoma, entrenar con `challenges/dataset/challenges_limpio.json`
   (no con el original) y revisar a mano los 117 retos del lote de IA que conservó el limpiador.
9. Crear bucket S3 + rol IAM, integrar con `boto3` — incluye conectar
   `challenge_generator.py` para subir los archivos generados a S3 en vez de dejarlos en
   `challenges/generated/` local.
10. Configurar la instancia EC2 siguiendo `docs/arquitectura_mvp.md`.
11. ~~App de escritorio con Electron~~ ✅ Hecho (22 oct) — ver "RETOMAR AQUÍ" y `electron/README.md`.
12. **Teoría, Módulos 4 y 6** — contenido a cargo del equipo (ver "RETOMAR AQUÍ").

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
