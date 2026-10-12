# WISPR — Pruebas de seguridad para el informe escrito

**Fecha de ejecución:** 12 de octubre de 2026.
**Qué se probó:** el backend FastAPI de este repositorio (rama `main`, commit `fc2c6bf`) conectado a
la base de datos real en Supabase, corriendo con `uvicorn` en `127.0.0.1:8000`, un solo worker, sin
SMTP (para no enviar correos a direcciones inventadas). Los usuarios de prueba se crearon solo para
estas pruebas y se borraron al terminar (Supabase quedó con 0 usuarios y los 10 retos del catálogo).

**Equipo de prueba:** Linux (Arch) con VS Code en Flatpak. Ahí **no hay Docker ni `nmap`**, por lo que
las pruebas de *Contenedor*, *Puertos con `nmap -sV`* y *Restauración* quedan **pendientes** de
ejecutar en la computadora donde se monta WISPR completo (Windows + Docker Desktop). Para esas se dejan
los comandos exactos y el resultado esperado según el código.

Los comandos se muestran con `curl` (Linux). En Windows es igual usando `curl.exe`.

## Resumen

> **Actualizado el 12 oct (después de corregir).** Las secciones de abajo guardan el resultado
> **inicial** de cada prueba. Las correcciones y los resultados al repetirlas están en el informe
> `docs/Informe_pruebas_seguridad_WISPR.docx`, y los parches del prototipo en `docs/parches/`.

| # | Prueba | Resultado inicial | Tras corregir | Estado |
|---|---|---|---|---|
| 1 | Permisos | Rutas privadas protegidas; no se puede actuar como otro jugador | Backend sin cambios; parche para `/api/kali/diagnose` del prototipo | ✅ |
| 2 | Datos incorrectos | 2 errores 500 + nombre con HTML aceptado (XSS) | Todo responde 400 con mensaje claro; XSS corregido (backend + parche frontend) | ✅ |
| 3 | Fuerza bruta | Bloqueo tras 5 fallos; sin límite por IP; enumeración por tiempo | + límite por IP/correo/jugador; tiempo constante (0,620 s contra 0,612 s) | ✅ |
| 4 | Contenedor | No ejecutable sin Docker | Resultado esperado documentado | ⏳ |
| 5 | Puertos | Solo 8000 en 127.0.0.1 | Confirmado: no accesible desde la red | ⏳ falta `nmap -sV` |
| 6 | Dependencias | 36 vulnerabilidades (pip) + 1 alta (npm) | **0** (pip, venv limpio) y **0** (npm con parche) | ✅ |
| 7 | Restauración | Falta la "sección 12" | BD: alembic 5,4 s + seed 6,8 s | ⏳ |

---

## 1. Permisos

```text
$ curl -i -H "Authorization: Bearer <token de jugador>" http://127.0.0.1:8000/api/kali/diagnose
HTTP/1.1 404 Not Found
{"detail":"Not Found"}

$ curl -i http://127.0.0.1:8000/api/ranking                       # sin sesión
HTTP/1.1 401 Unauthorized
{"ok":false,"auth":"required","error":"Tu sesión expiró o no es válida. Inicia sesión de nuevo."}

$ curl -i -H "Authorization: Bearer 0000…0000" http://127.0.0.1:8000/api/players/me   # token inventado
HTTP/1.1 401 Unauthorized
{"ok":false,"auth":"required", …}

$ curl -H "Authorization: Bearer <token del jugador 7>" "http://127.0.0.1:8000/api/players/me?playerId=1"
→ responde con los datos del jugador 7 (@pruebas), NO del 1
```

**Interpretación:**
- Toda ruta privada exige un token de sesión válido. El servidor guarda solo el hash SHA-256 del
  token, y la sesión se puede revocar.
- El servidor ignora el `playerId` que manda el navegador: el jugador sale siempre de la sesión, así
  que no se pueden ver ni modificar datos de otro jugador cambiando un número en la URL.
- `/api/kali/diagnose` responde 404 porque la terminal Kali todavía vive en el prototipo Node
  (`wispr_terminal_professional`) y no se migró a este backend. **Nota sobre el prototipo** (por
  lectura del código, no ejecutado): ahí esa ruta pide sesión, pero responde el diagnóstico de
  Docker a **cualquier** jugador con sesión, no solo a administradores. Para el informe conviene
  correr la prueba también contra el prototipo, o dejar dicho que al migrar la terminal esa ruta
  debe quedar solo para administradores.

## 2. Datos incorrectos

Registro (`POST /api/players/register`), cada campo por separado:

| Entrada | Respuesta | Evaluación |
|---|---|---|
| Nombre de 300 caracteres | 200, se recorta a 48 | ✅ |
| Usuario de 300 caracteres | 200, se limpia a `[a-z0-9._-]` y se recorta a 32 | ✅ |
| **Correo de 300 caracteres** | 200 al registrar, pero **500 al verificar el código** (la columna admite 255) | ❌ |
| **Contraseña de 300 caracteres** | **500 Internal Server Error** | ❌ |
| Contraseña vacía | 400 `"La contraseña debe tener al menos 4 caracteres."` | ✅ |
| `<script>alert(1)</script>` en usuario | Se limpia a `@scriptalert1script` | ✅ |
| `<script>alert(1)</script>` en correo | Se acepta (el formato de correo es muy permisivo) | ⚠️ |
| **`<script>alert(1)</script>` en nombre** | **Se acepta y se guarda tal cual** (también `<img src=x onerror=alert(1)>`) | ⚠️ |

Flag (`POST /api/submissions`, con sesión):

| Entrada | Respuesta |
|---|---|
| `""`, `"   "`, `null`, sin campo `flag`, `"WISPR{}"` | `{"ok":false,"error":"La flag debe tener el formato WISPR{...}."}`, no cuenta como intento ✅ |
| Cuerpo que no es JSON | `{"ok":false,"error":"El reto no existe o ya no está disponible."}` ✅ |

**Hallazgos:**

1. **Contraseña de más de 72 bytes → error 500.** bcrypt solo procesa 72 bytes. `security.py` rechaza
   correctamente las contraseñas más largas, pero el registro no valida el largo antes, y el error
   sale como 500 en vez de un mensaje claro. No compromete datos, pero un 500 es un fallo visible y
   llena el log. *Arreglo:* validar `len(password.encode()) <= 72` en el registro y responder 400.
2. **Correo de más de 255 caracteres → error 500 al verificar.** *Arreglo:* limitar el correo a 254
   caracteres (el máximo del estándar RFC 5321) en el registro.
3. **XSS almacenado posible en el frontend.** El backend guarda el nombre sin filtrar. Casi todo el
   frontend lo muestra de forma segura (crea nodos de texto con `h()`), **excepto** el gráfico
   "Puntos por estudiante" del profesor (`studentScoreChart` en `app.js`), que arma un SVG con
   `innerHTML` y mete el nombre sin escapar. Un estudiante llamado `<img src=x onerror=…>` podría
   ejecutar JavaScript en la sesión del **profesor** que abra ese gráfico y robar su token de
   `localStorage`. *Arreglo (las dos capas):* en el frontend, escapar el nombre en `studentScoreChart`
   (responsabilidad del equipo de frontend); en el backend, rechazar `<` y `>` en el nombre como
   defensa adicional. Hoy ese gráfico no se alimenta de este backend (la parte de grupos sigue en el
   prototipo), pero el nombre ya queda guardado, así que conviene arreglarlo antes de migrar grupos.

## 3. Fuerza bruta

```text
intento  1..10 (contraseña incorrecta): HTTP 401 {"ok":false,"error":"Usuario o contraseña incorrectos."}  (~0,8–1 s cada uno)
intento 11 con la contraseña CORRECTA:  HTTP 401 {"ok":false,"locked":true,"error":"Cuenta bloqueada temporalmente por intentos fallidos. Intenta de nuevo en ~15 min."}
usuario inexistente:                    HTTP 401 {"ok":false,"error":"Usuario o contraseña incorrectos."}
```

**Interpretación:**
- Tras **5 fallos en 15 minutos** la cuenta se bloquea **15 minutos**. Mientras dura, ni siquiera la
  contraseña correcta entra.
- El mensaje de error es el mismo para un usuario que existe y uno que no, así que un atacante no
  puede averiguar qué cuentas existen.
- Cada intento tarda ~1 s por el costo de bcrypt, lo que frena los ataques automatizados.
- Además, entrar exige el código de 6 dígitos enviado al correo (MFA): adivinar la contraseña no
  alcanza.
- **Límite conocido:** no hay límite de peticiones por IP. Un atacante puede rotar entre muchos
  usuarios distintos (5 intentos por cuenta), o pedir códigos de verificación repetidamente para
  llenar el correo de alguien. Está anotado como pendiente en `BACKEND-PENDIENTE.md` (punto 8). Se
  puede cubrir con un límite en nginx (`limit_req`) al desplegar, sin tocar código.

## 4. Contenedor (pendiente: requiere Docker)

Ejecutar en la terminal de WISPR (prototipo, con Docker Desktop):

```bash
whoami
ls -l /var/run/docker.sock
ping -c 2 <IP del router>
```

**Resultado esperado según el código** (`server.js`, `docker run` del contenedor Kali). Hay que
confirmarlo ejecutándolo:

| Comando | Esperado | Por qué |
|---|---|---|
| `whoami` | `kali` (no `root`) | `--user 1000:1000` |
| `ls -l /var/run/docker.sock` | `No such file or directory` | El socket de Docker no se monta. Solo se montan `/lab/challenges` (solo lectura) y `/workspace` |
| `ping -c 2 <router>` | Falla (`Network is unreachable` u `Operation not permitted`) | Red creada con `--internal` (sin salida), además de `--cap-drop ALL` |

Otras protecciones del contenedor: `--read-only`, `--security-opt no-new-privileges:true`,
`--pids-limit 256`, `--memory 2g`, `--cpus 2`.

## 5. Puertos

`nmap` no está instalado en el equipo de prueba. **Hay que correr `nmap -sV localhost` en la
computadora donde se monta WISPR** para el informe. Como aproximación se hizo un escaneo TCP de los
65 535 puertos de `127.0.0.1` con conexión y lectura del banner:

```text
 5355/tcp  (sin banner)                      → LLMNR, resolución de nombres del sistema operativo (no es WISPR)
 8000/tcp  HTTP/1.1 405 Method Not Allowed   → backend WISPR (uvicorn)
32164, 35871, 36645, 46079/tcp               → puertos temporales del editor y otros procesos locales (no son WISPR)
```

**Interpretación:** WISPR abre un solo puerto (8000), y solo en `127.0.0.1`, así que no es accesible
desde otras máquinas de la red. En el despliegue en AWS se mantiene así: nginx es lo único expuesto
(443) y le reenvía a uvicorn (ver sección **CONFIG AWS** de `docs/arquitectura_mvp.md`).

## 6. Dependencias

### `pip-audit -r requirements.txt` (backend)

36 vulnerabilidades únicas (69 entradas, con repetidas) en 7 paquetes:

| Paquete | Versión | Vulnerabilidades | Viene de | Acción recomendada |
|---|---|---|---|---|
| pillow | 10.4.0 | 17 | `together` (dependencia indirecta) | Actualizar `together` / fijar pillow ≥ 12.3.0 |
| starlette | 0.41.3 | 7 | `fastapi` | Actualizar `fastapi` (trae una starlette corregida, ≥ 1.3.1) |
| python-multipart | 0.0.20 | 6 | directa | Actualizar a ≥ 0.0.31 |
| python-jose | 3.3.0 | 3 | directa | **Quitar:** solo la usa el código JWT viejo de `security.py`; la app ya usa sesiones en BD |
| ecdsa | 0.19.2 | 1 (sin arreglo publicado) | `python-jose` | Desaparece al quitar `python-jose` |
| pytest | 8.3.4 | 1 | directa (solo pruebas) | Actualizar a ≥ 9.0.3; no corre en producción |
| scapy | 2.6.1 | 1 (sin arreglo publicado) | directa | Seguir el aviso; scapy solo genera archivos de retos, no recibe datos de usuarios |

Salida completa: correr `pip-audit -r requirements.txt` en `backend/`.

### `npm audit` (prototipo `wispr_terminal_professional`)

```text
nodemailer  <=10.0.8   Severity: high
  - Quoted local-part can produce malformed envelope recipient (GHSA-g57g-f23g-4646)
  - Quadratic backtracking in the addressparser (DoS) (GHSA-v53p-9fqp-m79j)
  - O(n^2) on comment-joined addresses (DoS) (GHSA-prgh-xp8r-p3m5)
1 high severity vulnerability — fix available via `npm audit fix`
```

**Interpretación:** solo afecta al prototipo Node. El backend FastAPI no usa nodemailer (envía con
`smtplib` de Python). Se corrige con `npm audit fix` en esa carpeta.

## 7. Restauración (pendiente)

La "sección 12" con los pasos de restauración no está en el repositorio ni en los documentos del
prototipo. Cuando se tenga, se ejecutan los pasos y se mide el tiempo. Como referencia, la
restauración de la base de datos de este backend es:

```bash
alembic -c migrations/alembic.ini upgrade head   # recrea las tablas
python -m app.db.seed_challenges                 # recarga los 10 retos y sus archivos
```

Medido el 12 oct contra Supabase (tablas ya existentes): `alembic` 5,4 s y el seed 6,8 s. Esto
mide solo la base de datos, no la restauración completa del sistema.
