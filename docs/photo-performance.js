/* MOTO TECH image rendering optimization — no data or upload changes. */
(()=>{
 'use strict';
 const seen=new WeakSet();
 let scheduled=false;
 const queue=new Set();
 const visible=el=>{
   const r=el.getBoundingClientRect();
   return r.width===0 || r.height===0 ||
     (r.top<innerHeight+240 && r.bottom>-240 && r.left<innerWidth+240 && r.right>-240);
 };
 const optimize=img=>{
   if(!(img instanceof HTMLImageElement)||seen.has(img))return;
   seen.add(img);
   img.decoding='async';
   if(!visible(img)){
     if(!img.hasAttribute('loading'))img.loading='lazy';
     if(!img.hasAttribute('fetchpriority'))img.fetchPriority='low';
   }
 };
 const scan=node=>{
   if(node.nodeType!==1)return;
   if(node.matches?.('img'))queue.add(node);
   node.querySelectorAll?.('img').forEach(img=>queue.add(img));
   if(!scheduled){
     scheduled=true;
     requestAnimationFrame(()=>{
       scheduled=false;
       for(const img of queue)optimize(img);
       queue.clear();
     });
   }
 };
 const boot=()=>{
   scan(document.body);
   const observer=new MutationObserver(records=>{
     for(const record of records)
       for(const node of record.addedNodes)scan(node);
   });
   observer.observe(document.body,{childList:true,subtree:true});
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
 else boot();
})();
