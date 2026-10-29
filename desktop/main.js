'use strict';
const {app, BrowserWindow, shell, ipcMain, session, Menu} = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const configPath = () => path.join(app.getPath('userData'), 'desktop-config.json');
function configuredUrl() {
  try { return JSON.parse(fs.readFileSync(configPath(), 'utf8')).url || null; }
  catch { return null; }
}
function validUrl(input) {
  try {
    const u = new URL(input);
    if (u.protocol !== 'https:' || !u.hostname || u.username || u.password) return null;
    if (u.hash) u.hash = '';
    return u.toString();
  } catch { return null; }
}
function allowed(target, home) {
  try { return new URL(target).origin === new URL(home).origin; }
  catch { return false; }
}
let win;
function createWindow() {
  win = new BrowserWindow({
    width:1440, height:900, minWidth:900, minHeight:650,
    backgroundColor:'#0d1118', autoHideMenuBar:true,
    title:'MOTO TECH — Мотосервис',
    webPreferences:{
      preload:path.join(__dirname,'preload.js'),
      contextIsolation:true, nodeIntegration:false,
      sandbox:true, webviewTag:false,
      partition:'persist:mototech'
    }
  });
  Menu.setApplicationMenu(null);
  const ses=win.webContents.session;
  // Permissions are limited to the configured application's own HTTPS origin.
  ses.setPermissionRequestHandler((wc, permission, callback, details) => {
    const home=configuredUrl();
    const requesting=details?.requestingUrl || wc.getURL();
    callback(Boolean(home && allowed(requesting,home) &&
      ['media','camera','microphone'].includes(permission)));
  });
  win.webContents.setWindowOpenHandler(({url}) => {
    const home=configuredUrl();
    if (home && allowed(url,home)) win.loadURL(url);
    else if (/^https:\/\//i.test(url)) shell.openExternal(url);
    return {action:'deny'};
  });
  win.webContents.on('will-navigate',(event,url)=>{
    const home=configuredUrl();
    if (!home || !allowed(url,home)) {
      event.preventDefault();
      if (/^https:\/\//i.test(url)) shell.openExternal(url);
    }
  });
  loadHome();
}
function loadHome(){
  const home=configuredUrl();
  if(home && validUrl(home)) win.loadURL(home).catch(()=>showSetup('Не удалось открыть адрес системы. Проверьте сеть и адрес.'));
  else showSetup();
}
function showSetup(message) {
  win.loadFile(path.join(__dirname,'setup.html'), {query:message?{error:message}:{}});
}
ipcMain.handle('desktop:save-url',async (event,input)=>{
  if(event.sender !== win?.webContents || !event.sender.getURL().startsWith('file:')) return {error:'Недопустимый запрос'};
  const url=validUrl(input);
  if(!url) return {error:'Нужен адрес действующей системы вида https://адрес-системы'};
  fs.mkdirSync(path.dirname(configPath()),{recursive:true});
  fs.writeFileSync(configPath(), JSON.stringify({url},null,2), {mode:0o600});
  loadHome();
  return {ok:true};
});
ipcMain.handle('desktop:reset-url',async(event)=>{
  if(event.sender !== win?.webContents || !event.sender.getURL().startsWith('file:')) return {error:'Недопустимый запрос'};
  try {fs.unlinkSync(configPath());}catch{}
  showSetup();
  return {ok:true};
});
app.whenReady().then(()=>{
  createWindow();
  app.on('activate',()=>{if(BrowserWindow.getAllWindows().length===0)createWindow()});
});
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit()});
