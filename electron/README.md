# WISPR — aplicación de escritorio (Electron)

Ventana de escritorio que abre la plataforma WISPR desde el servidor. No tiene lógica propia:
retos, terminal Kali, progreso y teoría viven en el servidor (nginx + FastAPI + Node + Docker),
así que la web y el escritorio se comportan igual.

## Usarla

Requiere Node.js 22 o superior.

```bash
cd electron
npm install          # la primera vez (descarga Electron, ~100 MB)
npm start            # abre WISPR en http://127.0.0.1:8787 (servidor local)
```

Para apuntar al servidor real, la variable `WISPR_URL`:

```powershell
# Windows (PowerShell)
$env:WISPR_URL = "https://wispr.training"; npm start
```

```bash
# Linux / macOS
WISPR_URL=https://wispr.training npm start
```

Si el servidor no responde, la app muestra «No se pudo conectar con WISPR» con un botón
«Reintentar».

## Instalador para Windows

```bash
npm run dist         # genera dist/WISPR-Setup.exe (~115 MB)
```

- La app instalada abre siempre `https://wispr.training` e ignora `WISPR_URL` (solo `npm start`
  la usa). La página se carga del servidor: un cambio en la web **no** obliga a recompilar.
  Solo hace falta un instalador nuevo si cambia algo de esta carpeta.
- Se publica en GitHub Releases del repo `WISPR`. La página de descarga de la web
  (`wispr.training/#descargar`) enlaza a `releases/latest/download/WISPR-Setup.exe`, así que
  basta con publicar un release nuevo con el archivo del mismo nombre:
  `gh release create vX.Y.Z dist/WISPR-Setup.exe` (subir antes `version` en `package.json`, y la
  versión que muestra `DESKTOP_DOWNLOAD` en `WISPR-frontend/app.js`).
- Sin firma digital: Windows muestra «Windows protegió su PC» la primera vez («Más información →
  Ejecutar de todas formas»). Firmarlo requiere un certificado de pago.
- Se instala por usuario (sin permisos de administrador), con acceso directo en el escritorio y en
  el menú Inicio, y se desinstala desde Configuración → Aplicaciones.

## Seguridad

- La página no tiene acceso a Node ni al sistema (`contextIsolation`, `sandbox`, sin
  `nodeIntegration`). El preload solo expone `window.wisprDesktop` (de solo lectura).
- Solo navega dentro de WISPR: cualquier enlace externo se abre en el navegador del sistema.
- Se niegan los permisos de cámara, micrófono, ubicación y notificaciones.
- Una sola ventana a la vez.

## Problemas conocidos

- **Se abre como Node y no muestra ventana** (por ejemplo, `electron --version` responde una
  versión `v24.x`): la variable de entorno `ELECTRON_RUN_AS_NODE` está definida. Pasa al lanzarla
  desde algunas extensiones de VS Code. Ábrela desde una terminal normal o quita la variable:
  `Remove-Item Env:ELECTRON_RUN_AS_NODE` (PowerShell).
