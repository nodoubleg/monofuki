'use strict';
// Production bridge / numerical oracle, NOT a font compiler or OpenType shaper.
// The actual transform and import-validation functions are extracted unchanged
// from the canonical playground app. A small VM isolates each settings instance.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const provenance=JSON.parse(fs.readFileSync(path.join(root,'src/tuning/provenance.json')));
for(const [name,sha]of Object.entries(provenance.source_files)){const actual=require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'src/tuning',name))).digest('hex');if(actual!==sha)throw Error('Tuning reference input drift: '+name);}
const app=fs.readFileSync(path.join(root,'website/tuning/app.js'),'utf8');
const slice=(a,b)=>{const start=app.indexOf(a),end=app.indexOf(b,start);if(start<0||end<0)throw Error('Canonical app boundaries changed');return app.slice(start,end)};
const prefix=app.slice(0,app.indexOf('function syncCrossbarControls()'));
const groups=slice('const groups=','for(const [id,title,test] of groups)');
const spacing=slice('function clampShift(','function draw(');
const validation=slice('function validateImport(','function applyImport(');
const data={
 'glyph-data':'src/tuning/glyphs.json',
 'accent-components':'src/tuning/accent-components.json',
 'g-alternatives':'src/tuning/g-alternatives.json',
 'glyph-alternatives':'src/tuning/alternatives.json'
};
function createEngine(settings){
 const nodes=Object.fromEntries(Object.entries(data).map(([id,file])=>[id,{textContent:fs.readFileSync(path.join(root,file),'utf8')}]));
 const ctx={document:{getElementById:id=>{if(!nodes[id])throw Error('Unexpected DOM access: '+id);return nodes[id]}}};
 vm.createContext(ctx);vm.runInContext(prefix+'\n'+groups+'\n'+spacing+'\n'+validation,ctx);
 const api=vm.runInContext(`({
  load(raw){spacingSafetyCache.clear();const v=validateImport(raw);for(const c of CHARS)state[c]=v.next[c];Object.assign(accentAdjustments,v.accents);Object.assign(sevenCrossbar,v.crossbar);Object.assign(glyphAlternatives,v.alternatives);Object.assign(pickerSections,v.sections);yJunctionRaise=v.junction;Object.assign(tailTruncation,v.tails);gDescenderCompression=v.compression;experiments=v.experiments;return true;},
  styles:[...STYLES],
  characters:style=>Object.keys(GLYPHS[style]),
  clusters,
  spacing:(text,style,strict=false)=>{const row=clusters(text);return {row,shifts:spacingShifts(row,style,strict)};},
  outline(style,c,original=false){
   const g=glyphFor(style,c,original?'original':alternativeFor(c));if(!g)return null;
   const a=original?null:adjustmentFor(c);
   return {character:c,style,advance:575,sourceBounds:g.b,
    p:g.p.map(([op,pts],i)=>[op,pts.map(([x,y])=>[horizontalPoint(x,y,c,g,i,a),accentPointY(y,c,g,i,a)])]),
    svgBody:pathFor(g,c,a),
    svgCrossbar:c==='7'&&!original?crossbarPath():'',
    alternative:original?'original':alternativeFor(c)};
  }
 })`,ctx);
 api.load(typeof settings==='string'?settings:JSON.stringify(settings));
 return api;
}
module.exports={createEngine};
if(require.main===module){
 const input=process.argv[2]||path.join(root,'src/tuning/defaults.json');
 const e=createEngine(fs.readFileSync(input,'utf8'));
 const result={kind:'Monofuki preview-transform reference, not a font binary',upm:1024,cell:{width:575,height:1150,ascent:880,descent:270},styles:{}};
 for(const style of e.styles)result.styles[style]=Object.fromEntries(e.characters(style).map(c=>[c,e.outline(style,c)]));
 process.stdout.write(JSON.stringify(result)+'\n');
}
