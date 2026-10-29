'use strict';
const {contextBridge,ipcRenderer} = require('electron');
if (location.protocol === 'file:') {
  contextBridge.exposeInMainWorld('motoDesktopSetup', {
    saveUrl:(url)=>ipcRenderer.invoke('desktop:save-url',url)
  });
}
