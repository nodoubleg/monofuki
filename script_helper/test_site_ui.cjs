'use strict';
// Focused state-transition regressions: exercise the shipped handlers in a VM.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};};
assert.match(read('website/playground.html'),/<option value="custom" disabled>/);
assert.doesNotMatch(read('website/playground.html'),/<\/option\s/);
async function selectionRace(){
 const nodes={'font-build':{value:'custom',querySelector:()=>({})},'font-status':{textContent:''},'retry-font':{},sample:{setAttribute(){}}},pending=deferred();
 const source=read('website/playground.js'),start=source.indexOf('let selectionRequest='),end=source.indexOf('async function start()',start);
 let renders=0;const fonts=new Set();
 const context=vm.createContext({byId:id=>nodes[id],loadCustom:()=>pending.promise,render:()=>renders++,document:{fonts,body:{classList:{add(){},remove(){}}}},MonofukiFonts:{loadDefault:()=>Promise.resolve('Monofuki')},family:'Monofuki'});
 vm.runInContext(source.slice(start,end),context);
 const custom=vm.runInContext('selectBuild()',context);nodes['font-build'].value='default';await vm.runInContext('selectBuild()',context);
 pending.resolve({fonts:[{family:'MonofukiCustom'}],profile:'test'});await custom;
 assert.equal(context.family,'Monofuki');assert.equal(nodes['font-build'].value,'default');assert.match(nodes['font-status'].textContent,/Monofuki default/);assert.equal(fonts.size,0);assert.equal(renders,1);
 const failure=deferred();context.loadCustom=()=>failure.promise;nodes['font-build'].value='custom';const request=vm.runInContext('selectBuild()',context);failure.reject(Error('storage unavailable'));await request;
 assert.equal(context.family,'Monofuki');assert.equal(nodes['font-build'].value,'default');assert.match(nodes['font-status'].textContent,/Monofuki default/);
 console.log('PASS custom/default race and failed selection stay consistent');
}
async function compilerRetry(){
 let attempts=0;const messages=[];
 const context=vm.createContext({URL,self:{location:'https://example.test/tuning/worker.js'},importScripts:()=>{attempts++;throw Error('temporary network failure');},postMessage:m=>messages.push(m),onmessage:null});
 vm.runInContext(read('website/tuning/worker.js'),context);
 await context.onmessage({data:{type:'build',payload:{}}});await context.onmessage({data:{type:'build',payload:{}}});
 assert.equal(attempts,2);assert.equal(messages.filter(m=>m.type==='error').length,2);assert.equal(vm.runInContext('runtime',context),null);
 console.log('PASS compiler initialization retries after transient failure');
}
async function workerStartup(){
 const nodes=Object.fromEntries(['build-fonts','build-status','cancel-build','test-build','build-family','default-download'].map(id=>[id,{disabled:false,hidden:true,value:'regular',addEventListener(){},focus(){}}]));let phase='constructor',attempts=0,terminated=0;
 const context=vm.createContext({document:{getElementById:id=>nodes[id]},Worker:function(){attempts++;if(phase==='constructor')throw Error('Worker denied');return {terminate(){terminated++;},postMessage(){if(phase==='post')throw Error('clone failure');}};},Error});
 vm.runInContext(read('website/tuning/download.js'),context);assert.equal(nodes['default-download'].href,'downloads/Monofuki.zip');nodes['build-family'].value='nerd';vm.runInContext('syncDefaultDownload()',context);assert.equal(nodes['default-download'].href,'downloads/MonofukiNerdFont.zip');vm.runInContext('productionPayload=()=>({settings:{}})',context);
 nodes['build-fonts'].onclick();assert.equal(nodes['build-fonts'].disabled,false);assert.equal(nodes['cancel-build'].hidden,true);assert.equal(vm.runInContext('buildBusy',context),false);assert.match(nodes['build-status'].textContent,/Worker denied/);
 phase='post';nodes['build-fonts'].onclick();assert.equal(nodes['build-fonts'].disabled,false);assert.equal(vm.runInContext('buildBusy',context),false);assert.equal(terminated,1);assert.match(nodes['build-status'].textContent,/clone failure/);
 phase='ok';nodes['build-fonts'].onclick();assert.equal(nodes['build-fonts'].disabled,true);nodes['cancel-build'].onclick();assert.equal(nodes['build-fonts'].disabled,false);assert.equal(vm.runInContext('buildBusy',context),false);assert.equal(terminated,2);assert.equal(attempts,3);
 console.log('PASS constructor, postMessage, retry and cancellation recovery');
}
async function fontLoading(){
 let missing=true,calls=0;
 const window={},document={fonts:{load:async spec=>{calls++;const [,style,weight]=spec.match(/^(normal|italic) (400|700)/);return missing?[]:[{family:'Monofuki',status:'loaded',weight,style}];}}};
 vm.runInNewContext(read('website/font-loading.js'),{window,document,Error});
 await assert.rejects(window.MonofukiFonts.loadDefault(),/could not be loaded/);
 missing=false;await window.MonofukiFonts.loadDefault();assert.equal(calls,8);
 await window.MonofukiFonts.loadDefault();assert.equal(calls,8);
 console.log('PASS missing font faces cannot report success, and loading retries');
}
async function failedCssFaceRetry(){
 const face={family:'Monofuki',status:'error'},fonts=[face];let recreated=0;
 fonts.load=async spec=>{if(face.status==='error')throw Error('cached network failure');const [,style,weight]=spec.match(/^(normal|italic) (400|700)/);return [{family:'Monofuki',status:'loaded',style,weight}];};
 const rule={type:5,cssText:'@font-face { font-family: Monofuki; src: url(fonts/Monofuki-Regular.woff2?v=pinned) }',style:{getPropertyValue:()=> 'Monofuki'}};
 const sheet={cssRules:[rule],deleteRule(i){assert.equal(i,0);},insertRule(css,i){assert.equal(css,rule.cssText);assert.equal(i,0);face.status='unloaded';recreated++;}};
 const window={};vm.runInNewContext(read('website/font-loading.js'),{window,document:{fonts,styleSheets:[sheet]},Error});
 await window.MonofukiFonts.loadDefault();assert.equal(recreated,1);
 await window.MonofukiFonts.loadDefault();assert.equal(recreated,1);
 console.log('PASS failed CSS faces are recreated with the same pinned URLs before retry');
}
async function customFaceAliases(){
 let close=0;const saved={Regular:new Uint8Array([1]),Bold:new Uint8Array([2]),Italic:new Uint8Array([3]),BoldItalic:new Uint8Array([4]),profile:'profile'};
 const db={transaction:()=>({objectStore:()=>({get:key=>{const q={};queueMicrotask(()=>{q.result=saved[key];q.onsuccess();});return q;}})}),close(){close++;}};
 const indexedDB={open:()=>{const request={result:db};queueMicrotask(()=>request.onsuccess());return request;}};
 const faces=[];const context=vm.createContext({indexedDB,Promise,ArrayBuffer,FontFace:function(family,bytes,descriptor){assert.equal(bytes.byteLength,1);assert.deepEqual(Object.keys(descriptor).sort(),['style','weight']);const face={family,load:async()=>face};faces.push(face);return face;},styles:{Regular:{weight:'400',style:'normal'},Bold:{weight:'700',style:'normal'},Italic:{weight:'400',style:'italic'},BoldItalic:{weight:'700',style:'italic'}},fontSerial:0});
 const source=read('website/playground.js');vm.runInContext(source.slice(source.indexOf('async function loadCustom()'),source.indexOf('let selectionRequest=')),context);
 const a=await vm.runInContext('loadCustom()',context),b=await vm.runInContext('loadCustom()',context);
 assert.notEqual(a.family,b.family);assert.equal(a.fonts.length,4);assert.equal(b.fonts.length,4);assert.equal(close,2);
 console.log('PASS saved builds use fresh four-style aliases and owned ArrayBuffers');
}
function defaultContract(){
 const defaults=JSON.parse(read('src/tuning/defaults.json'));
 const match=read('website/tuning/app.js').match(/^const APPROVED_DEFAULTS=(.*);$/m);
 assert.deepEqual(JSON.parse(match[1]),defaults);assert.equal(defaults.glyphAlternatives.q,'tailed');
 assert.match(read('website/tuning/template.html'),/font-loading\.js/);
 assert.match(read('website/tuning/template.html'),/href="style\.css"/);
 assert.match(read('website/tuning/template.html'),/Monofuki default/);
 assert.match(read('website/playground.html'),/Monofuki default/);
 assert.doesNotMatch(read('website/playground.js'),/Greg[’']s/);
 console.log('PASS Monofuki default settings, q selection, shared font loading and labels');
}
(async()=>{defaultContract();await fontLoading();await failedCssFaceRetry();await customFaceAliases();await selectionRace();await compilerRetry();await workerStartup();})().catch(e=>{console.error(e);process.exitCode=1;});
