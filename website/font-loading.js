'use strict';
// A resolved FontFaceSet.load([]) means no matching face, not a loaded font.
// Load before assigning a face to editable controls; WebKit may otherwise keep
// painting the first fallback face until the control's font changes again.
window.MonofukiFonts=(()=>{
 const styles={Regular:{weight:'400',style:'normal',suffix:'Regular'},Bold:{weight:'700',style:'normal',suffix:'Bold'},Italic:{weight:'400',style:'italic',suffix:'Italic'},BoldItalic:{weight:'700',style:'italic',suffix:'Bold-Italic'}};
 let defaultLoad;
 function resetFailedFaces(){
  if(!Array.from(document.fonts).some(face=>face.family.replace(/["']/g,'')==='Monofuki'&&face.status==='error'))return;
  // FontFace.load() retains its rejection. Recreate the same-origin CSS rules
  // so a Retry starts fresh faces while preserving the hashed source URLs.
  for(const sheet of document.styleSheets){
   let rules;try{rules=sheet.cssRules;}catch{continue;}
   for(let i=rules.length-1;i>=0;i--){
    const rule=rules[i];
    if(rule.type!==5||rule.style.getPropertyValue('font-family').replace(/["']/g,'').trim()!=='Monofuki')continue;
    const css=rule.cssText;sheet.deleteRule(i);sheet.insertRule(css,i);
   }
  }
 }
 async function loadDefault(){
  if(!defaultLoad){resetFailedFaces();defaultLoad=Promise.all(Object.values(styles).map(async s=>{
   const faces=await document.fonts.load(`${s.style} ${s.weight} 28px "Monofuki"`,'Agq0');
   if(!faces.some(f=>f.family.replace(/["']/g,'')==='Monofuki'&&f.status==='loaded'&&f.weight===s.weight&&f.style===s.style))throw Error('Monofuki could not be loaded. Check your connection and retry.');
   return faces;
  })).catch(error=>{defaultLoad=null;throw error;});}
  await defaultLoad;return 'Monofuki';
 }
 function apply(element,family,descriptor){
  element.style.fontFamily=`"${family}", ui-monospace, monospace`;
  element.style.fontWeight=descriptor.weight;element.style.fontStyle=descriptor.style;
  element.style.fontSynthesis='none';
 }
 return {styles,loadDefault,apply};
})();
