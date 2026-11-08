# WISPR — Estado del proyecto

Actualizado el 7 de noviembre de 2026. EXPOTEC es el **12 de noviembre**. Resume qué funciona, qué
tecnologías se usan de verdad, cómo correr la app y qué falta. Si otro documento dice algo distinto,
vale este.

## Qué ya funciona

| Parte | Estado | Cómo se comprobó |
|---|---|---|
| Registro y login con código por correo | Listo | Tests y prueba real con Supabase y Gmail |
| Retos, flags, puntos y ranking | Listo | Tests y prueba real con Supabase |
| Dificultad adaptativa | Lista | Tests y prueba real con Supabase |
| Historias de los retos con IA | Listas | Prueba real con Together AI |
| Terminal Kali en Docker | Lista | Prueba con Docker real |
| Terminal Kali dentro de Electron | Lista | Confirmado por el equipo (1 nov) |
| Interfaces de profesor y admin | Listas | Confirmado por el equipo (1 nov) |
| Teoría, módulos 1 a 6 | Listos | Los 6 módulos están en `WISPR-frontend/app.js` |
| Foto de perfil con avatares de Wisp | Lista | Tests y prueba real con Supabase |
| Botón de idioma español/inglés | Listo en la interfaz | Probado en navegador (2 nov) |
| Contraseña segura al registrarse | Lista | Tests y prueba en navegador (2 nov) |
| Etiquetas de técnicas de MITRE | Listas | Prueba en navegador (2 nov) |
| Informe al resolver un reto y estrellas | Listos | Tests, navegador y Supabase real (2 nov) |
| Voucher para cuentas admin | Listo | Tests y prueba en navegador (2 nov) |
| Plataforma web en AWS (`https://wispr.training`) | En línea con HTTPS | `http` → 301 a `https`, `https` → 200, CORS correcto (7 nov) |
| Dominio `wispr.training` y `www` | Apunta solo a la EC2 | DNS revisado en Google, Cloudflare y GoDaddy (7 nov) |
| Terminal por el dominio | Node ya acepta `wispr.training` y `www` | Comprobado desde fuera el 7 nov; falta una sesión completa |
| Ícono propio en la pestaña y en Electron | En línea | El dominio sirve el favicon (7 nov) |
| Laboratorios que se liberan solos | En la EC2 | Docker simulado, 22 comprobaciones; falta una sesión con Docker real |
| Instalador de Windows (`WISPR-Setup.exe`) | Publicado en GitHub Releases `v1.0.0` | Enlace de descarga 200 y SHA-256 igual al compilado (7 nov); falta probar el asistente completo |
| Página de descarga (`wispr.training/#descargar`) | En línea | Navegador: 3 anchos, 2 temas, inglés (7 nov) |
| Portada: modo claro, responsive y textos nuevos | En línea | Navegador: 360 a 1366 px, 2 temas (7 nov) |
| Cronómetro progresivo en los retos | En línea | Navegador, con tiempos simulados (7 nov) |
| Puntos con bonos en Perfil, Inicio y encabezado | En GitHub, falta en la EC2 | Navegador con un jugador simulado (7 nov) |

El botón traduce la interfaz: página de inicio, registro, retos, terminal, perfil, paneles, recorrido
de Wisp y mensajes de error. Quedan en español el contenido de las lecciones de Teoría, las historias
de los retos, lo que imprime `ctf` dentro de Kali y los correos.

## Tecnologías en uso

| Área | Tecnología | Para qué sirve |
|---|---|---|
| Aplicación | Electron | Convierte WISPR en una aplicación de escritorio |
| Interfaz | HTML, CSS y JavaScript | Crean las pantallas, los retos, la teoría y los paneles |
| Terminal | xterm.js | Muestra la terminal dentro de la aplicación |
| Terminal | Node.js y node-pty | Node.js sirve la interfaz y conecta la terminal con Kali; node-pty ejecuta la sesión |
| Backend | Python y FastAPI | Manejan cuentas, sesiones, retos, flags, puntos, ranking y grupos |
| Backend | SQLAlchemy y Alembic | SQLAlchemy conecta Python con la base de datos; Alembic aplica los cambios a sus tablas |
| Base de datos | Supabase (PostgreSQL) | Guarda usuarios, retos, intentos, progreso y grupos |
| Laboratorio | Docker | Crea contenedores aislados para cada jugador |
| Laboratorio | Kali Linux | Da al jugador las herramientas para resolver los retos |
| Ciberseguridad | Wireshark, TShark y Aircrack-ng | Analizan capturas de red y recuperan contraseñas Wi-Fi |
| Ciberseguridad | Scapy | Genera los archivos `.pcap` de algunos retos |
| Inteligencia artificial | Together AI (Muse Glimmer 30B) | Escribe el título, la descripción y la pista de cada reto |
| Seguridad | bcrypt | Protege las contraseñas guardándolas como hash |
| Correo | Gmail SMTP | Envía los códigos de verificación de 6 dígitos |
| Nube | AWS EC2 y Security Group | EC2 es el servidor que alojará WISPR; el Security Group es su firewall |
| Nube | nginx | Recibe las conexiones y las envía a FastAPI o a Node.js |

La técnica, la dificultad y la flag de cada reto las decide el código, no la IA.

**No se usan, aunque aparezcan en otros documentos:**

- React, Tailwind y Chart.js.
- Amazon S3 y CloudWatch.
- Pandas y scikit-learn: la dificultad adaptativa funciona con reglas.
- LoRA: se intentó, pero no se usa.

## Decisión sobre Amazon S3

No se usa S3 para EXPOTEC. WISPR corre en una sola EC2 y FastAPI sirve los archivos de los retos
desde su disco. Integrarlo no mejora la demo y agrega `boto3`, un bucket, permisos de IAM y otro
servicio que puede fallar.

- **Cuándo usarlo:** con varias instancias que compartan archivos, o si los archivos deben
  conservarse aunque se elimine el servidor.
- **Mientras tanto:** apagar la EC2 con **Stop**, no con Terminate. Stop conserva el disco; Terminate
  puede borrarlo junto con los archivos generados.
- **En la defensa:** presentarlo como mejora futura, no como parte de la arquitectura actual.

## Cómo correr la app en local

Primero abrir **Docker Desktop**. Luego usar tres terminales de PowerShell, en este orden.

**Terminal 1: backend**

```powershell
cd "C:\Users\Jathniel Navarrete\WISPR\backend"
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

**Terminal 2: frontend y Kali**

```powershell
cd "C:\Users\Jathniel Navarrete\WISPR-frontend"
node server.js
```

**Terminal 3: app de escritorio**

```powershell
cd "C:\Users\Jathniel Navarrete\WISPR\electron"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
npm start
```

Para usar el navegador, omitir la terminal 3 y abrir <http://127.0.0.1:8787>.

Para abrir la app de escritorio contra el servidor real, no hacen falta las terminales 1 y 2:

```powershell
cd "C:\Users\Jathniel Navarrete\WISPR\electron"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
$env:WISPR_URL = "https://wispr.training"; npm start
```

Las rutas son las de esta PC; en otra computadora hay que cambiarlas. Las terminales deben quedar
abiertas mientras se usa la app. `Ctrl + C` detiene cada servicio.

## Qué falta

### Imprescindible

1. **Terminar el despliegue en AWS.** La web funciona en `https://wispr.training` (DNS limpio y
   HTTPS desde el 7 nov), con FastAPI y Node como servicios y las imágenes de Kali construidas. La IP
   sola (`http://3.140.124.203`) ya no sirve: se entra por el dominio. Detalle y pasos en
   `docs/DESPLIEGUE-AWS.md`. Falta:
   - Traer a la EC2 el arreglo de los puntos (`63a0e38`): `cd ~/WISPR-frontend && git pull && sudo
     systemctl restart wispr-web`. Probar una sesión completa de la terminal por el dominio.
   - Probar el instalador completo: descargarlo desde `wispr.training/#descargar`, instalar, entrar
     y abrir la terminal Kali.
   - Confirmar que el certificado se renueva solo: `sudo certbot renew --dry-run`.
   - Emitir un voucher nuevo para `admin_wispr`, porque el actual quedó escrito en un chat.
2. **Preparar la EC2 para el día de EXPOTEC.** Cada laboratorio Kali puede usar hasta ~0,9 GB de
   RAM. En la t3.medium (4 GB) caben 3; con la demo más los jueces conviene pasar a **t3.large**
   (8 GB) ese día y poner `MAX_LAB_ENVIRONMENTS=6`. Cuesta aproximadamente US$1 más por día. El
   límite solo afecta la terminal: cualquiera puede entrar a la página aunque esté lleno.
3. **Ensayar la demo completa en la máquina final, por el dominio:** registro, retos, terminal,
   profesor, admin y teoría.

### Para la defensa

4. **Corregir `docs/arquitectura_mvp.md`.** Todavía describe S3, CloudWatch y JWT, y no incluye Node.
   La arquitectura real está en `docs/diagrama_red.md`.
5. **Corregir la lista de tecnologías de `CLAUDE.md`.** Todavía menciona React, Tailwind, Chart.js,
   Pandas y S3. La lista real es la de este documento.

### Opcional

- **Firmar el instalador:** sin firma, Windows muestra «Windows protegió su PC» la primera vez (la
  página de descarga lo explica). Un certificado cuesta entre US$100 y US$400 al año.
- **Página más liviana:**
  - Activar `gzip` en nginx para JS, CSS y JSON. Hoy la EC2 los manda sin comprimir (medido el
    7 nov): `app.js` bajaría de 749 KB a 187 KB y `style.css`, de 182 KB a 35 KB.
  - Recodificar el video de fondo (`img/fondo.mp4`, 10,4 MB) o cambiarlo por una imagen. Los videos
    de «Voces del CTF» solo cargan sus datos básicos hasta que alguien los reproduce.

### Después de EXPOTEC

- **Archivos Wi-Fi por jugador:** hoy todos reciben el mismo archivo y pueden pasarse la flag. Hay
  que resolverlo antes de usar WISPR para poner notas reales.
- **Retos para un grupo:** el profesor solo puede publicar un reto para todos los estudiantes.
- **Motivo del nivel:** mostrarle al jugador por qué le subió o le bajó la dificultad.
- **Otras integraciones:** S3, CloudWatch, análisis con Pandas y LoRA.
