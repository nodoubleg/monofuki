'use strict';
const byId=id=>document.getElementById(id),samples={
code:'#!/usr/bin/env python3\nfrom pathlib import Path\n\ndef choose_font(profile):\n    glyphs = ["Ag0MW", "mwgy", "Il1|0O"]\n    return {"family": "Monofuki", "profile": profile}\n\nif __name__ == "__main__":\n    print(choose_font("curved braces"))',
prose:'The quick brown fox jumps over the lazy dog.\n\nA font is a small thing you spend a lot of time looking at. Try a paragraph, a tricky word, or a line you know by heart.\n\nÁÉÅÜ Ñ Ö Ì Ç Ľ · áéåü ñöìç · 0123456789\nBright vixens jump; dozy fowl quack.',
symbols:'┌─────────────────────┐\n│ Monofuki / symbols  │\n└─────────────────────┘\n⠁ ⠃ ⠇ ⡇ ⣿  █ ▄ ▀ ▌ ▐\n← → ↑ ↓ ⇨ ⇩ ↔  ∑ ∞ ≠ ≤ ≥\n0 O 1 l I |   g q y j   { } 7\n\nSystem emoji: 😀 👩‍💻 🏳️‍🌈 ❤️ ⚡',
spacing:'minimum Toffee vivid AVATAR\nVVA VYA WYA · illi WWW 111\n\na ... b   a :: b   x -> y\na === b   x += 1   a != b\n\n+------------+------------+\n| fixed      | advances   |\n+------------+------------+'
};
const FONT_LEADING=1150/1024;
let currentSample='code',family='Monofuki';
const styles={Regular:{weight:'400',style:'normal',suffix:'Regular'},Bold:{weight:'700',style:'normal',suffix:'Bold'},Italic:{weight:'400',style:'italic',suffix:'Italic'},BoldItalic:{weight:'700',style:'italic',suffix:'Bold-Italic'}};
byId('sample').value=samples.code;
function render(){
 const chosen=styles[byId('font-style').value],size=byId('font-size').value,leading=byId('leading').value,kern=byId('font-kern').checked;
 Object.assign(byId('sample').style,{fontFamily:`"${family}", ui-monospace, monospace`,fontWeight:chosen.weight,fontStyle:chosen.style,fontSize:size+'px',lineHeight:leading,fontKerning:kern?'normal':'none',fontFeatureSettings:`"kern" ${kern?1:0}`});
 byId('font-size-output').textContent=size+' px';byId('leading-output').textContent=Math.abs(Number(leading)-FONT_LEADING)<1e-9?'Font default · 1:2':Number(leading).toFixed(2)+' em';
 const container=byId('style-comparison');container.replaceChildren();
 for(const [name,s]of Object.entries(styles)){const article=document.createElement('article'),heading=document.createElement('h2'),text=document.createElement('pre');heading.textContent=name.replace('BoldItalic','Bold italic');text.textContent=byId('sample').value;Object.assign(text.style,{fontFamily:`"${family}", ui-monospace, monospace`,fontWeight:s.weight,fontStyle:s.style,fontSize:size+'px',lineHeight:leading,fontKerning:kern?'normal':'none',fontFeatureSettings:`"kern" ${kern?1:0}`});article.append(heading,text);container.append(article);}
}
for(const id of ['font-style','font-size','leading','font-kern'])byId(id).addEventListener('input',render);
byId('sample').addEventListener('input',render);
byId('reset-leading').onclick=()=>{byId('leading').value=FONT_LEADING;render();};
for(const button of document.querySelectorAll('[data-sample]'))button.onclick=()=>{currentSample=button.dataset.sample;byId('sample').value=samples[currentSample];for(const b of document.querySelectorAll('[data-sample]'))b.setAttribute('aria-pressed',String(b===button));render();};
byId('reset-sample').onclick=()=>{byId('sample').value=samples[currentSample];render();};
async function loadCustom(){
 const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('monofuki-playground',1);request.onupgradeneeded=()=>request.result.createObjectStore('fonts');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
 const values=await Promise.all([...Object.keys(styles),'profile'].map(key=>new Promise((resolve,reject)=>{const q=db.transaction('fonts').objectStore('fonts').get(key);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);})));db.close();
 const fonts=values.slice(0,4);if(fonts.some(f=>!f))throw Error('Build a font in the customizer first.');
 const loaded=await Promise.all(Object.entries(styles).map(async([style,descriptor],i)=>{const font=new FontFace('MonofukiCustom',fonts[i],descriptor);await font.load();return font;}));
 return {fonts:loaded,profile:values[4]||''};
}
let selectionRequest=0;
async function selectBuild(){
 const generation=++selectionRequest,choice=byId('font-build').value;
 try{
  if(choice==='custom'){
   byId('font-status').textContent='Loading your generated build…';
   const custom=await loadCustom();
   if(generation!==selectionRequest||byId('font-build').value!==choice)return;
   for(const font of document.fonts)if(font.family==='MonofukiCustom')document.fonts.delete(font);
   for(const font of custom.fonts)document.fonts.add(font);
   byId('font-build').querySelector('[value=custom]').textContent='Your build '+custom.profile;
   family='MonofukiCustom';
  }else family='Monofuki';
  render();byId('font-status').textContent=choice==='custom'?'Your generated build · four real styles · 575-unit advances':'Greg’s current defaults · four real styles · 575-unit advances';
 }catch(e){
  if(generation!==selectionRequest||byId('font-build').value!==choice)return;
  family='Monofuki';byId('font-build').value='default';render();
  byId('font-status').textContent='Showing Greg’s defaults. '+e.message;
 }
}
byId('font-build').onchange=selectBuild;

async function start(){
 try{for(const s of Object.values(styles))await document.fonts.load(`${s.style} ${s.weight} 28px Monofuki`);if(!selectionRequest)byId('font-status').textContent='Greg’s current defaults · four real styles · 575-unit advances';}
 catch{if(!selectionRequest)byId('font-status').textContent='Font loading failed. Please reload.';}
 try{const custom=await loadCustom(),option=byId('font-build').querySelector('[value=custom]');option.disabled=false;option.textContent='Your build '+custom.profile;if(location.hash==='#custom'&&!selectionRequest){byId('font-build').value='custom';await selectBuild();}}catch{}
 render();
}
render();start();
