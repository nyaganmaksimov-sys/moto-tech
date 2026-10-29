/* MOTO TECH offline outbox, integration foundation.
   Call enqueue only for explicit, authenticated, allowlisted app changes.
   This module does NOT intercept existing Supabase requests. */
export function createOfflineOutbox({scope, send, onStatus=()=>{}}){
  if(!scope || !/^[a-zA-Z0-9:_-]{8,180}$/.test(scope))throw Error('An authenticated user/device scope is required');
  if(typeof send!=='function')throw Error('send(change) callback is required');
  const databaseName='moto-tech-offline-v1';
  let flushing=false;
  function openDB(){
    return new Promise((resolve,reject)=>{
      const req=indexedDB.open(databaseName,1);
      req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains('outbox'))db.createObjectStore('outbox',{keyPath:'id'});};
      req.onsuccess=()=>resolve(req.result);
      req.onerror=()=>reject(req.error);
    });
  }
  async function transaction(mode,operation){
    const db=await openDB();
    return new Promise((resolve,reject)=>{
      const tx=db.transaction('outbox',mode),store=tx.objectStore('outbox');
      let result;
      try {result=operation(store);}catch(err){db.close();reject(err);return;}
      tx.oncomplete=()=>{db.close();resolve(result);};
      tx.onerror=()=>{db.close();reject(tx.error);};
      tx.onabort=()=>{db.close();reject(tx.error||new Error('Transaction aborted'));};
    });
  }
  async function list(){
    const db=await openDB();
    try {return await new Promise((resolve,reject)=>{
      const tx=db.transaction('outbox','readonly'),req=tx.objectStore('outbox').getAll();
      req.onsuccess=()=>resolve(req.result.filter(item=>item.scope===scope).sort((a,b)=>a.createdAt-b.createdAt));
      req.onerror=()=>reject(req.error);
    });}finally{db.close();}
  }
  async function save(change){await transaction('readwrite',store=>store.put(change));}
  async function remove(id){await transaction('readwrite',store=>store.delete(id));}
  async function status(){
    const items=await list();
    const result={queued:items.filter(x=>x.status==='queued').length,
      conflicts:items.filter(x=>x.status==='conflict').length,
      failed:items.filter(x=>x.status==='failed').length};
    onStatus(result);return result;
  }
  async function enqueue({kind,entityId,payload,baseVersion=null}){
    if(!['work-status','mechanic-work-note','part-request','crm-comment'].includes(kind))
      throw Error('Operation not on the offline allowlist');
    if(!entityId || typeof entityId!=='string')throw Error('Entity ID required');
    const id=crypto.randomUUID();
    const change={id,scope,kind,entityId,payload:structuredClone(payload),
      baseVersion,createdAt:Date.now(),status:'queued',attempts:0};
    await save(change);await status();return id;
  }
  async function flush(){
    if(flushing||!navigator.onLine)return await status();
    flushing=true;
    try{
      const items=await list();
      for(const item of items){
        if(item.status==='conflict'||item.status==='failed')continue;
        if(!navigator.onLine)break;
        try{
          // Server MUST enforce user authorization, idempotency by item.id,
          // and optimistic concurrency via baseVersion for updates.
          const result=await send({...item});
          if(result?.status==='conflict'){
            await save({...item,status:'conflict',message:'Changed on server; manual review required'});
            continue;
          }
          if(result?.status!=='applied')throw Error('No confirmed server acknowledgement');
          await remove(item.id);
        }catch(err){
          if(err?.code==='NOT_AUTHORIZED'||err?.code==='VALIDATION_ERROR'){
            await save({...item,status:'failed',message:String(err.message||err)});
          }else{
            await save({...item,attempts:item.attempts+1,lastAttemptAt:Date.now(),status:'queued'});
            // Preserve ordering; do not send later dependent edits until retry.
            break;
          }
        }
      }
    }finally{flushing=false;await status();}
  }
  function begin(){
    const online=()=>{void flush();};
    window.addEventListener('online',online);
    return ()=>window.removeEventListener('online',online);
  }
  return {enqueue,flush,list,status,begin};
}
