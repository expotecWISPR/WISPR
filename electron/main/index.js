/**
 * WISPR — aplicación de escritorio.
 *
 * La app es una ventana segura que abre la plataforma desde el servidor
 * (nginx + FastAPI + Node + Docker, ver docs/arquitectura_mvp.md). No contiene
 * lógica propia: retos, terminal Kali y progreso viven en el servidor, así que
 * web y escritorio se comportan igual y no hay que mantener dos versiones.
 *
 * Dirección del servidor: variable de entorno WISPR_URL (por ejemplo
 * https://wispr.ejemplo.com). Sin ella, el servidor local de desarrollo.
 */

const path = require("node:path");
const { app, BrowserWindow, session, shell } = require("electron");

const DEFAULT_URL = "http://127.0.0.1:8787";

function appUrl() {
  const raw = (process.env.WISPR_URL || DEFAULT_URL).trim();
  try {
    const url = new URL(raw);
    if (url.protocol === "https:" || url.protocol === "http:") return url;
  } catch { /* se usa la dirección por defecto */ }
  console.error(`WISPR_URL inválida (${raw}); se usa ${DEFAULT_URL}`);
  return new URL(DEFAULT_URL);
}

const APP_URL = appUrl();
const OFFLINE_PAGE = path.join(__dirname, "offline.html");

function isAppUrl(target) {
  try { return new URL(target).origin === APP_URL.origin; } catch { return false; }
}

// Enlaces que salen de WISPR (documentación, sitios externos): se abren en el
// navegador del sistema, nunca dentro de la app.
function openOutside(target) {
  try {
    const url = new URL(target);
    if (url.protocol === "https:" || url.protocol === "http:") shell.openExternal(url.toString());
  } catch { /* enlace inválido: se ignora */ }
}

function showOffline(win) {
  win.loadFile(OFFLINE_PAGE, { query: { url: APP_URL.toString() } });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1366,
    height: 860,
    minWidth: 400,
    minHeight: 600,
    title: "WISPR",
    backgroundColor: "#081a3a",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "index.js"),
      // La página no tiene acceso a Node ni al sistema operativo.
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true
    }
  });

  win.once("ready-to-show", () => win.show());

  // Solo se navega dentro de WISPR (o de la pantalla sin conexión hacia WISPR).
  win.webContents.on("will-navigate", (event, target) => {
    if (isAppUrl(target)) return;
    event.preventDefault();
    openOutside(target);
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!isAppUrl(url)) openOutside(url);
    return { action: "deny" };
  });

  // Servidor apagado o sin red: pantalla propia con "Reintentar" en vez de la
  // página de error en blanco de Chromium. Solo para la página principal.
  win.webContents.on("did-fail-load", (_event, code, _description, url, isMainFrame) => {
    if (isMainFrame && code !== -3 && isAppUrl(url)) showOffline(win); // -3 = navegación cancelada
  });

  win.loadURL(APP_URL.toString());
}

// Una sola ventana de WISPR a la vez.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const [win] = BrowserWindow.getAllWindows();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(() => {
    // WISPR no necesita cámara, micrófono, ubicación ni notificaciones.
    session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
    createWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}
