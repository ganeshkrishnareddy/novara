'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('novaraDesktop', Object.freeze({
  getState: () => ipcRenderer.invoke('desktop:getState'),
  saveSettings: (patch) => ipcRenderer.invoke('desktop:saveSettings', patch),
  restartBackend: () => ipcRenderer.invoke('desktop:restartBackend'),
  openSettings: () => ipcRenderer.invoke('desktop:openSettings'),
  openExternal: (url) => ipcRenderer.invoke('desktop:openExternal', url),
  onStatus: (callback) => {
    if (typeof callback !== 'function') return () => {};
    const listener = (_event, state) => callback(state);
    ipcRenderer.on('desktop:status', listener);
    return () => ipcRenderer.removeListener('desktop:status', listener);
  }
}));
