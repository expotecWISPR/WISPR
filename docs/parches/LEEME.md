# Parches de seguridad para `wispr_terminal_professional` (frontend + servidor Node)

Salen de las pruebas de seguridad del 12 oct 2026 (`docs/pruebas_seguridad.md`). Se prepararon y
verificaron sobre **copias** de los archivos.

> **✅ Aplicados el 12 oct 2026** en `/home/lonsoo/wispr_terminal_professional` (con autorización del
> equipo). Respaldo de los originales en `/home/lonsoo/wispr_terminal_professional_respaldo_2026-10-12/`
> (`app.js`, `server.js`, `package.json`, `package-lock.json`, `node_modules/nodemailer` y sus
> SHA-256). Para deshacer: copiar esos archivos de vuelta a la carpeta del prototipo.
>
> Verificado después de aplicar: `node --check` de ambos archivos; `npm audit` → 0 vulnerabilidades
> (el lockfile solo cambió nodemailer); el servidor arranca y responde (prueba hecha sobre una copia,
> con `node-pty` sustituido porque su binario es solo para Windows/Mac); `/api/kali/diagnose` con
> sesión de estudiante ya no muestra versiones y el segundo pedido inmediato da 429; en el navegador,
> registrarse con contraseña de 5 caracteres muestra "La contraseña debe tener entre 8 y 64
> caracteres." y la página no tiene errores de JavaScript.
>
> Si en otra computadora hay una copia del prototipo sin estos cambios, se aplican así:

## Cómo aplicarlos (en otra copia del prototipo)

Desde la carpeta `wispr_terminal_professional` (hacer una copia de respaldo antes):

```bash
git apply --verbose /ruta/a/WISPR/docs/parches/frontend-app.js.patch
git apply --verbose /ruta/a/WISPR/docs/parches/frontend-server.js.patch
npm install nodemailer@10.0.11
```

`git apply` funciona aunque la carpeta no sea un repositorio (en Windows viene con Git for Windows).
En Linux/Mac también sirve `patch -p1 < archivo.patch`.

## Qué corrige cada uno

| Archivo | Problema | Cómo se verificó |
|---|---|---|
| `frontend-app.js.patch` | **XSS almacenado:** el gráfico "Puntos por estudiante" del profesor (`studentScoreChart`) metía el nombre del estudiante en `innerHTML` sin escapar. Un nombre como `<img src=x onerror=…>` ejecutaba código en la sesión del profesor. Agrega `escapeMarkup()`. También: el registro pide 8–64 caracteres de contraseña, igual que el backend | En Chromium (Playwright): con el código original el script del atacante **se ejecuta**; con el parche **no**, y el nombre se ve como texto |
| `frontend-server.js.patch` | `/api/kali/diagnose` mostraba a **cualquier** jugador las versiones de Docker, Node y el sistema operativo del host, y se podía pedir sin límite (cada pedido lanza ~8 comandos `docker`). Ahora: versiones solo para administradores, el estudiante ve solo su contenedor, y máximo 1 diagnóstico cada 10 s por jugador | `node --check` + la función `diagnose` ejecutada con un Docker simulado (estudiante vs. admin) |
| `npm install nodemailer@10.0.11` | `nodemailer <= 10.0.8`: 1 vulnerabilidad **alta** (3 avisos: sobre de correo mal formado y 2 DoS) | `npm audit` → `found 0 vulnerabilities`; `sendMail` probado con `jsonTransport` |

---

# `terminal-modo-conectado.patch` — terminal Kali conectada a FastAPI (12 oct 2026)

> **✅ Aplicado el 12 oct 2026** en `/home/lonsoo/wispr_terminal_professional`. Respaldo de los
> archivos de antes en `/home/lonsoo/wispr_terminal_professional_respaldo_2026-10-12_conexion/`
> (`server.js`, `kali/ctf`, `.env.example` y sus SHA-256). Se aplica **encima** de los parches de
> seguridad de arriba. En otra copia: `git apply --verbose /ruta/a/WISPR/docs/parches/terminal-modo-conectado.patch`.

**Problema:** el frontend solo puede hablar con un servidor. Con FastAPI no había terminal; con Node,
la terminal validaba sesiones y flags contra sus propios archivos (`lab/data/*.json`), sin ver las
cuentas ni los puntos de Supabase.

**Qué cambia** (solo si se define `WISPR_BACKEND_URL`; sin ella el prototipo funciona igual que antes):

| Archivo | Cambio |
|---|---|
| `server.js` | Cada token se valida preguntándole a FastAPI (`GET /api/players/me`); si FastAPI no responde, Node contesta 503 y no abre la terminal (falla cerrado). Al activar un reto baja de FastAPI el catálogo y los archivos (los mismos de la web) al workspace del jugador. Cada `ctf submit` se reenvía a `POST /api/submissions` con el token del propio jugador y `source: "terminal"`. Cada 60 s revisa que la sesión de una terminal abierta siga valiendo (logout o bloqueo → la cierra). Las rutas `/api/*` que no son de la terminal se reenvían a FastAPI, para poder probar sin nginx. `WISPR_PUBLIC_HOSTS` acepta el dominio público como origen. CSP permite `wss:`. |
| `kali/ctf` | `ctf show` ya no dice "evidencia única para tu cuenta" cuando el archivo es el mismo para todos (`sharedEvidence` en `active.json`). Requiere reconstruir la imagen Kali. |
| `.env.example` | Documenta `WISPR_BACKEND_URL`, `WISPR_PUBLIC_HOSTS` y `SESSION_RECHECK_SECONDS`. |

**Cómo se probó** (Linux, con `node-pty` compilado y un Docker simulado que usa carpetas como
contenedores; FastAPI con una base SQLite temporal, sin tocar Supabase ni mandar correos):
30 comprobaciones de punta a punta (registro a través de Node, activar reto, terminal real,
`ctf show`/`ctf submit`, puntos y ranking en FastAPI, token falso → 401/403, origen ajeno → 403,
`//otro-host` no desvía el reenvío, logout → terminal cerrada con código 4401); UI real en Chromium
(registro → Abrir Kali → `ctf submit` → "Reto resuelto", 120 pts, sin errores de JavaScript);
FastAPI caído → 503/502 sin caerse; y el modo de siempre (sin la variable) sigue validando por su
cuenta. **Falta probarlo con Docker real.**

**Cómo correrlo en una computadora sin nginx** (p. ej. Windows con Docker Desktop):
1. Backend: desde `WISPR/backend`, `venv\Scripts\python.exe -m uvicorn main:app --port 8000`.
2. Prototipo: en su `.env`, `WISPR_BACKEND_URL=http://127.0.0.1:8000`; luego `node server.js`.
3. Abrir `http://127.0.0.1:8787` (Node sirve el frontend y reenvía el resto de la API a FastAPI).
