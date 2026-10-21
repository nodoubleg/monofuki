'use strict';
let buildWorker, buildBusy=false, builtFonts={};
const familySelect=document.getElementById('build-family'),defaultDownload=document.getElementById('default-download');
function syncDefaultDownload(){const nerd=familySelect.value==='nerd';defaultDownload.href='downloads/'+(nerd?'MonofukiNerdFont':'Monofuki')+'.zip';defaultDownload.title=nerd?'Default Monofuki Nerd Font — four styles':'Default Monofuki — four styles';}
familySelect.addEventListener('change',syncDefaultDownload);syncDefaultDownload();
function productionPayload(){
  const styles={};
  for(const style of STYLES){
    styles[style]={};
    for(const c of Object.keys(GLYPHS[style])){
      const g=glyphFor(style,c),a=adjustmentFor(c);
      styles[style][c]={character:c,advance:575,sourceBounds:g.b,
        p:g.p.map(([op,pts],i)=>[op,pts.map(([x,y])=>[horizontalPoint(x,y,c,g,i,a),accentPointY(y,c,g,i,a)])]),
        svgCrossbar:c==='7'?crossbarPath():''};
    }
  }
  // Reading text and dock state are local UI; only the standard sample is shared.
  const configuration=settings();configuration.sample=STANDARD_PREVIEW;
  return {styles,settings:configuration,family:document.getElementById('build-family').value};
}
function saveDownload(data,name,type){const url=URL.createObjectURL(new Blob([data],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
document.getElementById('build-fonts').onclick=()=>{
  if(buildBusy)return;
  const button=document.getElementById('build-fonts'),status=document.getElementById('build-status');
  const fail=error=>{buildWorker?.terminate();buildWorker=null;builtFonts={};buildBusy=false;button.disabled=false;document.getElementById('cancel-build').hidden=true;status.textContent='Build stopped: '+(error.message||String(error))+'. You can retry or use the default download.';};
  let payload;try{payload=productionPayload();}catch(error){fail(error);return;}
  buildBusy=true;builtFonts={};button.disabled=true;
  document.getElementById('cancel-build').hidden=false;
  status.textContent='Preparing the choices selected when you clicked Build…';
  try{buildWorker ||= new Worker('tuning/worker.js');}catch(error){fail(error);return;}
  buildWorker.onmessage=async({data})=>{
    if(data.type==='progress')status.textContent=data.text;
    if(data.type==='font'){
      builtFonts[data.style]=data.bytes;
    }
    if(data.type==='complete'){
      buildBusy=false;document.getElementById('cancel-build').hidden=true;
      saveDownload(data.bytes,`${data.family}-${data.identity.slice(0,8)}.zip`,'application/zip');
      status.textContent='Your four styles are ready. The ZIP includes OTF, TTF, WOFF2, settings and notices.';
      try{await savePlaygroundFonts(builtFonts,data.identity.slice(0,8));document.getElementById('test-build').hidden=false;}catch{status.textContent+=' Your browser could not save the playground copy.';}
      buildBusy=false;button.disabled=false;document.getElementById('cancel-build').hidden=true;
    }
    if(data.type==='error')fail(Error(data.text));
  };
  buildWorker.onerror=()=>fail(Error('The compiler could not start'));
  try{buildWorker.postMessage({type:'build',payload});}catch(error){fail(error);}

};
document.getElementById('cancel-build').onclick=()=>{if(!buildBusy)return;buildWorker?.terminate();buildWorker=null;builtFonts={};buildBusy=false;document.getElementById('build-fonts').disabled=false;document.getElementById('cancel-build').hidden=true;document.getElementById('build-status').textContent='Build cancelled. Your previous playground build is still available.';document.getElementById('build-fonts').focus();};
async function savePlaygroundFonts(fonts,profile){
  if(!['Regular','Bold','Italic','BoldItalic'].every(style=>fonts[style]?.byteLength>0))throw Error('Incomplete font family');
  const database=await new Promise((resolve,reject)=>{const request=indexedDB.open('monofuki-playground',1);request.onupgradeneeded=()=>request.result.createObjectStore('fonts');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
  await new Promise((resolve,reject)=>{const tx=database.transaction('fonts','readwrite');for(const [style,bytes] of Object.entries(fonts))tx.objectStore('fonts').put(bytes,style);tx.objectStore('fonts').put(profile,'profile');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Storage transaction aborted'));});database.close();
}
