// Actual pinned renderer functions with owned React/OS producers; no GUI claim.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const React=require('./node_modules/react'),{act,create}=require('./node_modules/react-test-renderer'),ts=require('./node_modules/typescript');
global.IS_REACT_ACT_ENVIRONMENT=true;
const V=path.resolve(__dirname,'..'),fixture='fixtures/pinned/host',patched='.qa/patched-host';
const component=name=>p=>React.createElement(name,p,p.children);
const primitives=new Proxy({cx:(...a)=>a.filter(Boolean).join(' ')},{get:(o,k)=>o[k]??component(k)});
let surface,network=[],timers=new Map(),nextTimer=1,invalidations=[],visibility=[],disposed=[];
const windowStub={setTimeout:(f,ms)=>{const n=nextTimer++;timers.set(n,{f,ms});return n;},clearTimeout:n=>timers.delete(n),tezbar:{
 extensionSearchTextChanged:p=>new Promise((resolve,reject)=>network.push({type:'search',p,resolve,reject})),
 extensionInvokeAction:p=>new Promise((resolve,reject)=>network.push({type:'action',p,resolve,reject})),
 extensionLoadMore:p=>new Promise(resolve=>network.push({type:'more',p,resolve})),
 extensionDisposeSession:p=>{disposed.push(p);return Promise.resolve({ok:true});},
 onExtensionSessionInvalidated:fn=>{invalidations.push(fn);return()=>{};},onWindowVisibility:fn=>{visibility.push(fn);return()=>{};},
}};
function load(rel,root,imports){
 const source=fs.readFileSync(path.join(V,root,rel),'utf8');
 const js=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 const module={exports:{}};
 const ctx=vm.createContext({module,exports:module.exports,require:id=>{if(id==='react')return React;if(id in imports)return imports[id];throw Error('Forbidden renderer import '+id);},React,Error,window:windowStub,console:{log(){},error(){}},setTimeout:windowStub.setTimeout,clearTimeout:windowStub.clearTimeout, navigator:{clipboard:{writeText(){throw Error('Forbidden real clipboard');}}}},{codeGeneration:{strings:false,wasm:false}});
 new vm.Script(js,{filename:'PINNED/'+rel}).runInContext(ctx,{timeout:2000});return module.exports;
}
const listPath='src/renderer/src/raycast-api/list-runtime.tsx',parentPath='src/renderer/ExtensionRuntimeView.tsx';
function list(root){return load(listPath,root,{'../../ui/primitives':primitives,'../../ui/Markdown':{Markdown:component('Markdown')},'./detail-runtime':{MetadataItem:component('MetadataItem'),MetadataSidebar:component('MetadataSidebar')},'../../colorConverter':{buildColorConversionResults:()=>[]}}).ListRuntime;}
function parent(root,List){return load(parentPath,root,{'./ui/primitives':primitives,'./extensionSessionRefresh':{startSessionRefresh:()=>()=>{}},'./src/raycast-api':{ExtensionRuntimeSurface:p=>{surface=p;return React.createElement(List,{...p,onRunPrimaryAction:p.onInvokeAction,onOpenActions:()=>{}});}}}).default;}
function result(q='',title='initial',sessionId='s'){return {ok:true,mode:'view',title:'OneLook Thesaurus',sessionId,extensionId:'com.tezbar.native.onelook-thesaurus',commandName:'search',generation:'owned',refreshMs:null,actions:[{id:'toggle',title:'Toggle Definitions'}],root:{type:'List',props:{searchText:q,__hasServerSearch:true},children:[{type:'List.Item',props:{id:'1',title,actionIds:['toggle']}}]}};}
const settle=fn=>act(async()=>{await fn?.();await Promise.resolve();});
const checks=[];
(async()=>{
 // Retain a demonstrated baseline failure: input event does not dispatch until
 // a timer fires, leaving the parent's ownership counter unchanged meanwhile.
 let B=list(fixture),P=parent(fixture,B),r;
 await settle(()=>{r=create(React.createElement(P,{initial:result(),onBack(){}}));});
 await settle(()=>r.root.findByType('input').props.onChange({target:{value:'A'}}));assert.equal(network.length,0);assert.ok([...timers.values()].some(t=>t.ms===200));checks.push('baseline reproduced: server input ownership waits behind debounce');
 await settle(()=>r.unmount());network=[];timers.clear();
 B=list(patched);P=parent(patched,B);
 await settle(()=>{r=create(React.createElement(P,{initial:result(),onBack(){}}));});
 const input=()=>r.root.findByType('input');
 await settle(()=>input().props.onChange({target:{value:'A'}}));assert.equal(network.length,1);const a=network.shift();assert.equal(surface.root.props.isLoading,true);
 await settle(()=>input().props.onChange({target:{value:'B'}}));const b=network.shift();
 await settle(()=>input().props.onChange({target:{value:'A'}}));const anew=network.shift();
 await settle(()=>a.resolve(result('A','old-A')));assert.equal(input().props.value,'A');assert.equal(surface.root.children[0].props.title,'initial');
 await settle(()=>b.resolve(result('B','old-B')));assert.equal(surface.root.children[0].props.title,'initial');
 await settle(()=>anew.resolve(result('A','new-A')));assert.equal(surface.root.children[0].props.title,'new-A');assert.equal(surface.root.props.isLoading,false);checks.push('patched synchronous A/B/A revisions reject same-text old A and late B; pending indicator follows current request');
 await settle(()=>input().props.onChange({target:{value:'invalid'.repeat(1000)}}));const invalid=network.shift();
 await settle(()=>input().props.onChange({target:{value:''}}));const empty=network.shift();
 await settle(()=>invalid.resolve({ok:false,message:'old invalid'}));assert.equal(input().props.value,'');await settle(()=>empty.resolve(result('','empty')));checks.push('invalid intermediate and empty draft fence old errors');
 await settle(()=>input().props.onChange({target:{value:'error'}}));const failure=network.shift();await settle(()=>failure.resolve({ok:false,message:'owned-error'}));assert.ok(r.root.findAll(n=>n.type==='Message').some(n=>n.props.children==='owned-error'));
 await settle(()=>input().props.onChange({target:{value:'recovered'}}));const recovery=network.shift();await settle(()=>recovery.resolve(result('recovered','recovered')));assert.ok(!r.root.findAll(n=>n.type==='Message').some(n=>n.props.children==='owned-error'));checks.push('current failure visible; successful next search clears old error');
 // Pending option/action response may not replace a newer draft/result.
 let actionPromise;await settle(()=>{actionPromise=surface.onInvokeAction('toggle',{value:'owned-option'});});const option=network.shift();
 await settle(()=>input().props.onChange({target:{value:'after-option'}}));const after=network.shift();await settle(()=>option.resolve(result('recovered','old-option')));assert.equal(input().props.value,'after-option');await settle(()=>after.resolve(result('after-option','current')));await actionPromise;checks.push('pending action result cannot overwrite edited draft; source has no dropdown options');
 let inertPromise;await settle(()=>{inertPromise=surface.onInvokeAction('stale');});const inert=network.shift();await settle(()=>inert.resolve({ok:true,mode:'unchanged'}));await inertPromise;assert.equal(surface.root.children[0].props.title,'current');checks.push('unchanged stale action preserves current view');
 await settle(()=>input().props.onChange({target:{value:'throw'}}));const thrown=network.shift();await settle(()=>thrown.reject(Error('owned rejected promise')));assert.ok(r.root.findAll(n=>n.type==='Message').some(n=>n.props.children==='owned rejected promise'));checks.push('rejected search promise becomes recoverable visible error');
 await settle(()=>input().props.onChange({target:{value:'cross'}}));const cross=network.shift();await settle(()=>r.update(React.createElement(P,{initial:result('','new-session','s2'),onBack(){}})));await settle(()=>cross.resolve(result('cross','old-session')));assert.equal(surface.sessionId,'s2');assert.equal(input().props.value,'');checks.push('cross-session response cannot restore prior draft');
 await settle(()=>r.unmount());
 fs.writeFileSync(path.join(V,'evidence/renderer.json'),JSON.stringify({checks,count:checks.length,pinnedHost:'ea100cee3f69711de12485ba061950c5fc65258f',patchAppliedToHost:false,actualFunctions:true,ownedProducers:true,GUI:false},null,2)+'\n');
 console.log('RENDERER QA:',checks.length,'checks, actual pinned input/reconciliation functions; patch remains unapplied');
})().catch(e=>{console.error(e);process.exitCode=1;});
