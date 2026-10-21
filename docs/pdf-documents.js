// MOTO TECH — PDF generation and secure Supabase archive for signed documents.
const TYPES={intake:"Акт приёма-передачи",order:"Заказ-наряд",completed:"Акт выполненных работ",handover:"Акт выдачи техники"};
const $=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text??"—");if(parent)parent.append(n);return n};
function section(root,title){return $("h2",title,root)}
async function loadPDFLibrary(){
 if(window.html2pdf)return;
 await new Promise((resolve,reject)=>{const s=document.createElement("script");s.src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.2/html2pdf.bundle.min.js";s.onload=resolve;s.onerror=()=>reject(new Error("Не удалось загрузить генератор PDF"));document.head.append(s)});
}
export async function archiveRepairPdf({db,staff,order,kind}){
 if(!TYPES[kind])throw new Error("Неизвестный тип документа");
 if(!["owner_manager","manager","administrator"].includes(staff.role))throw new Error("Доступ к сохранению PDF только у руководителей");
 const [c,v,lines,hand,logs]=await Promise.all([
 db.from("customers").select("full_name,phone").eq("id",order.customer_id).single(),
 db.from("vehicles").select("brand,model,vin,plate,year,mileage").eq("id",order.vehicle_id).single(),
 db.from("order_cost_items").select("item_type,name,quantity,unit_price").eq("order_id",order.id).order("created_at"),
 db.from("repair_handovers").select("*").eq("order_id",order.id).maybeSingle(),
 db.from("repair_work_log").select("kind,description").eq("order_id",order.id).order("created_at")
 ]);
 for(const r of [c,v,lines,hand,logs])if(r.error)throw r.error;
 if(kind==="handover"&&!hand.data)throw new Error("Сначала оформите выдачу");
 if(kind==="completed"&&!lines.data.length)throw new Error("Сначала заполните смету");
 await loadPDFLibrary();
 const root=$("div");root.style.cssText="position:fixed;left:-10000px;top:0;width:740px;padding:32px;background:white;color:#151515;font:15px Arial,sans-serif;line-height:1.5;z-index:-1";
 const head=$("div","MOTO TECH",root);head.style.cssText="font-size:30px;font-weight:800;border-bottom:3px solid #b92d3b;padding-bottom:12px;color:#161616";
 $("h1",TYPES[kind],root);$("p","Заказ № "+(order.order_number||"—")+" · "+new Date(order.created_at).toLocaleDateString("ru-RU"),root);
 section(root,"Владелец и техника");$("p","Клиент: "+c.data.full_name+" · Телефон: "+(c.data.phone||"—"),root);
 $("p","Мотоцикл: "+[v.data.brand,v.data.model].filter(Boolean).join(" ")+" · VIN: "+(v.data.vin||"не указан"),root);
 $("p","Год: "+(v.data.year||"—")+" · Госномер: "+(v.data.plate||"—")+" · Пробег: "+(v.data.mileage||"—"),root);
 $("p","Причина обращения: "+(order.complaint||"—"),root);
 if(kind==="intake"){section(root,"Сведения о приёмке");$("p","Состояние, повреждения и комплектность мотоцикла проверяются и фиксируются сторонами при передаче. Фотографии сохраняются в электронной карточке техники.",root)}
 if(kind==="order"||kind==="completed"){
 section(root,kind==="order"?"Смета":"Работы и материалы");
 const table=$("table",undefined,root);table.style.cssText="border-collapse:collapse;width:100%;font-size:13px";
 const header=$("tr",undefined,table);for(const h of ["Тип","Наименование","Кол-во","Цена, ₽","Итого, ₽"]){const th=$("th",h,header);th.style.cssText="border:1px solid #999;padding:5px;text-align:left"}
 let total=0;
 for(const item of lines.data){const tr=$("tr",undefined,table);const sum=Number(item.quantity)*Number(item.unit_price);total+=sum;for(const t of [item.item_type==="work"?"Работа":"Запчасть",item.name,item.quantity,Number(item.unit_price).toFixed(2),sum.toFixed(2)]){const td=$("td",t,tr);td.style.cssText="border:1px solid #aaa;padding:5px"}}
 $("h2","Итого: "+total.toFixed(2)+" ₽",root);
 if(kind==="completed"){section(root,"Записи о выполнении");for(const item of logs.data.filter(x=>x.kind==="work"))$("p","• "+item.description,root)}
 }
 if(kind==="handover"){section(root,"Выдача");for(const line of ["Получатель: "+hand.data.customer_name,"Состояние: "+hand.data.vehicle_condition,"Комплектность: "+hand.data.returned_items,"Оплачено: "+hand.data.paid_amount+" ₽","Дата: "+new Date(hand.data.issued_at).toLocaleString("ru-RU")])$("p",line,root)}
 const sign=$("p","Представитель сервиса: ______________    Клиент: ______________",root);sign.style.marginTop="55px";
 $("p","Документ требует проверки и фактических подписей сторон. Реквизиты исполнителя уточняются перед выдачей юридически значимых документов.",root).style.cssText="font-size:10px;color:#777;margin-top:32px";
 document.body.append(root);
 try{
 const blob=await window.html2pdf().set({margin:7,filename:"MOTO-TECH-"+kind+".pdf",image:{type:"jpeg",quality:0.96},html2canvas:{scale:2,backgroundColor:"#fff"},jsPDF:{unit:"mm",format:"a4",orientation:"portrait"},pagebreak:{mode:["css","legacy"]}}).from(root).outputPdf("blob");
 if(!blob||blob.size<1000)throw new Error("Не удалось сформировать PDF");
 const user=(await db.auth.getUser()).data.user;if(!user)throw new Error("Авторизация истекла");
 const path=user.id+"/"+crypto.randomUUID()+".pdf";
 const upload=await db.storage.from("moto-documents-private").upload(path,blob,{contentType:"application/pdf",upsert:false});if(upload.error)throw upload.error;
 const result=await db.from("repair_documents").insert({order_id:order.id,vehicle_id:order.vehicle_id,document_type:kind,file_path:path,filename:"MOTO-TECH-"+kind+"-"+order.order_number+".pdf",uploaded_by:staff.id});
 if(result.error){await db.storage.from("moto-documents-private").remove([path]);throw result.error}
 return true;
 }finally{root.remove()}
}