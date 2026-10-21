'use strict';
// Focused state-transition regressions: exercise the shipped handlers in a VM.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};};
assert.match(read('website/playground.html'),/<option value="custom" disabled>/);
assert.doesNotMatch(read('website/playground.html'),/<\/option\s/);
async function selectionRace(){
 const nodes={'font-build':{value:'custom',querySelector:()=>({})},'font-status':{textContent:''}},pending=deferred();
 const source=read('website/playground.js'),start=source.indexOf('let selectionRequest='),end=source.indexOf('async function start()',start);
 let renders=0;const fonts=new Set();
 const context=vm.createContext({byId:id=>nodes[id],loadCustom:()=>pending.promise,render:()=>renders++,document:{fonts},family:'Monofuki'});
 vm.runInContext(source.slice(start,end),context);
 const custom=vm.runInContext('selectBuild()',context);nodes['font-build'].value='default';await vm.runInContext('selectBuild()',context);
 pending.resolve({fonts:[{family:'MonofukiCustom'}],profile:'test'});await custom;
 assert.equal(context.family,'Monofuki');assert.equal(nodes['font-build'].value,'default');assert.match(nodes['font-status'].textContent,/current defaults/);assert.equal(fonts.size,0);assert.equal(renders,1);
 const failure=deferred();context.loadCustom=()=>failure.promise;nodes['font-build'].value='custom';const request=vm.runInContext('selectBuild()',context);failure.reject(Error('storage unavailable'));await request;
 assert.equal(context.family,'Monofuki');assert.equal(nodes['font-build'].value,'default');assert.match(nodes['font-status'].textContent,/Showing Greg’s defaults/);
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
(async()=>{await selectionRace();await compilerRetry();await workerStartup();})().catch(e=>{console.error(e);process.exitCode=1;});
