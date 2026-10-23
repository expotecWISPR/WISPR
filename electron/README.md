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
$env:WISPR_URL = "https://wispr.ejemplo.com"; npm start
```

```bash
# Linux / macOS
WISPR_URL=https://wispr.ejemplo.com npm start
```

Si el servidor no responde, la app muestra «No se pudo conectar con WISPR» con un botón
«Reintentar».

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
- Todavía no hay instalador (`.exe`): para la demo basta `npm start`. Si hace falta, se puede
  empaquetar después con `electron-builder`.
