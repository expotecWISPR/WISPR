# WISPR — Estado del proyecto

Actualizado el 1 de noviembre de 2026. Resume qué funciona, qué tecnologías se usan de verdad, cómo
correr la app y qué falta. Si otro documento dice algo distinto, vale este.

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

Las rutas son las de esta PC; en otra computadora hay que cambiarlas. Las terminales deben quedar
abiertas mientras se usa la app. `Ctrl + C` detiene cada servicio.

## Qué falta

### Imprescindible

1. **Desplegar en AWS.** No hay registro de que esté hecho. Falta:
   - Crear la EC2 y configurar nginx.
   - Activar HTTPS con `certbot` y poner el dominio.
   - Usar el Session Pooler de Supabase.
   - Correr `alembic upgrade head` y `python -m app.db.seed_challenges`.
   - Construir la imagen de Kali desde cero.
   - Dejar Node funcionando como servicio.
2. **Ensayar la demo completa en la máquina final:** registro, retos, terminal, profesor, admin y
   teoría.

### Para la defensa

3. **Corregir `docs/arquitectura_mvp.md`.** Todavía describe S3, CloudWatch y JWT, y no incluye Node.
   La arquitectura real está en `docs/diagrama_red.md`.
4. **Corregir la lista de tecnologías de `CLAUDE.md`.** Todavía menciona React, Tailwind, Chart.js,
   Pandas y S3. La lista real es la de este documento.

### Opcional

- **Instalador `.exe`:** solo hace falta para instalar la app en otras computadoras.

### Después de EXPOTEC

- **Archivos Wi-Fi por jugador:** hoy todos reciben el mismo archivo y pueden pasarse la flag. Hay
  que resolverlo antes de usar WISPR para poner notas reales.
- **Retos para un grupo:** el profesor solo puede publicar un reto para todos los estudiantes.
- **Motivo del nivel:** mostrarle al jugador por qué le subió o le bajó la dificultad.
- **Otras integraciones:** S3, CloudWatch, análisis con Pandas y LoRA.
