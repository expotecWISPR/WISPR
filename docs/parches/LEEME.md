# Parches de seguridad para `wispr_terminal_professional` (frontend + servidor Node)

Salen de las pruebas de seguridad del 12 oct 2026 (`docs/pruebas_seguridad.md`). Se prepararon y
verificaron sobre **copias** de los archivos: el prototipo no está en Git, así que no se modificó
directamente. Los aplica el equipo dueño de ese código.

## Cómo aplicarlos

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
