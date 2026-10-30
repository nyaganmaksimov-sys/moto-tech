'use strict';
const {contextBridge,ipcRenderer} = require('electron');
if (location.protocol === 'file:') {
  contextBridge.exposeInMainWorld('motoDesktopSetup', {
    saveUrl:(url)=>ipcRenderer.invoke('desktop:save-url',url)
  });
}
// Optimize only the MOTO TECH page. Actual uploads and image URLs stay with the web app.
if (location.protocol === 'https:' &&
    location.hostname === 'nyaganmaksimov-sys.github.io' &&
    location.pathname.startsWith('/moto-tech/')) {
  const prepare = img => {
    if (!(img instanceof HTMLImageElement) || img.dataset.mtImageOptimized) return;
    img.dataset.mtImageOptimized = '1';
    img.decoding = 'async';
    const r=img.getBoundingClientRect();
    const offscreen=r.width>0 && r.height>0 &&
      (r.top>innerHeight+180 || r.bottom< -180);
    if (offscreen && !img.hasAttribute('loading')) img.loading='lazy';
    if (offscreen && !img.hasAttribute('fetchpriority')) img.fetchPriority='low';
  };
  const scan = node => {
    if(node.nodeType!==1) return;
    if(node.tagName==='IMG') prepare(node);
    node.querySelectorAll?.('img').forEach(prepare);
  };
  const start = () => {
    scan(document.documentElement);
    const observer=new MutationObserver(records=>{
      for(const record of records) for(const node of record.addedNodes) scan(node);
    });
    observer.observe(document.documentElement,{subtree:true,childList:true});
  };
  if(document.documentElement) start();
  else document.addEventListener('DOMContentLoaded',start,{once:true});
}
