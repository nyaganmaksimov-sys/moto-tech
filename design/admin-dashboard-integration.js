/* MOTO TECH layout enhancement. Must load AFTER the existing module has authenticated and defined selectView/startQuickIntake. Integration script for workspace.html, not a standalone file. */
function installAdminDashboardLayout({staff,selectView,startQuickIntake,closeMobileMenu,loadOverview}) {
 if(!staff||!['owner_manager','manager','administrator'].includes(staff.role))return;
 if(document.querySelector('#mtMobileBottom'))return;
 document.body.classList.add('mt-admin');
 const $=id=>document.getElementById(id);
 const bottom=document.createElement('nav');bottom.id='mtMobileBottom';bottom.setAttribute('aria-label','Мобильное меню');
 for(const [view,symbol,label] of [['overview','⌂','Главная'],['orders','▤','Заказы'],['storage_records','▣','Хранение'],['menu','☰','Меню']]){
  const b=document.createElement('button');b.type='button';b.dataset.mtView=view;
  const ico=document.createElement('span');ico.textContent=symbol;b.append(ico,document.createTextNode(label));
  b.addEventListener('click',()=>{if(view==='menu'){$('mobileNavToggle')?.click();return}closeMobileMenu();window.motoOrderFilter=null;selectView(view)});
  bottom.append(b)
 }
 document.body.append(bottom);
 const actions=document.createElement('div');actions.className='mt-admin-actions';
 const intake=document.createElement('button');intake.type='button';intake.textContent='＋ Новая приёмка';
 const orders=document.createElement('button');orders.type='button';orders.className='secondary';orders.textContent='Все заказ-наряды';orders.onclick=()=>{window.motoOrderFilter=null;selectView('orders')};
 actions.append(intake,orders);$('overviewStatusCards')?.before(actions);
 const cover=document.createElement('div');cover.className='mt-intake-picker';cover.hidden=true;
 const dialog=document.createElement('div');dialog.className='mt-intake-dialog';dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');
 const close=document.createElement('button');close.type='button';close.className='mt-close';close.textContent='✕';close.onclick=()=>cover.hidden=true;
 const title=document.createElement('h3');title.textContent='Новая приёмка';dialog.append(close,title);
 for(const [kind,label] of [['repair','Ремонт'],['storage','Хранение'],['both','Ремонт + хранение']]){
  const button=document.createElement('button');button.type='button';button.className='mt-choice';button.textContent=label;
  button.onclick=()=>{cover.hidden=true;startQuickIntake(kind)};dialog.append(button)
 }
 cover.append(dialog);cover.onclick=e=>{if(e.target===cover)cover.hidden=true};document.body.append(cover);
 intake.onclick=()=>cover.hidden=false;
 document.addEventListener('keydown',e=>{if(e.key==='Escape')cover.hidden=true});
 const sidebar=$('sidebar');sidebar?.addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;bottom.querySelectorAll('[data-mt-view]').forEach(x=>x.classList.toggle('active',x.dataset.mtView===b.dataset.view))});
}
