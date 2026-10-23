/**
 * Preload de WISPR. Corre aislado de la página (contextIsolation + sandbox) y
 * solo expone datos de solo lectura: la página puede saber que corre en la app
 * de escritorio, pero no obtiene ningún acceso a Node ni al sistema.
 */

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("wisprDesktop", Object.freeze({
  isDesktop: true,
  platform: process.platform,
  electron: process.versions.electron
}));
