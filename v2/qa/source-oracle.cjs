// Runs trusted pinned TSX and the locked utils closure in a closed VM.
// Network, fs, child processes and host UI are replaced BEFORE module evaluation.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const React = require('./node_modules/react');
const {act,create} = require('./node_modules/react-test-renderer');
const ts = require('./node_modules/typescript');
const v2 = path.resolve(__dirname,'..');
global.IS_REACT_ACT_ENVIRONMENT = true;
const modules = new Map();
for (const name of fs.readdirSync(path.join(v2,'fixtures/pinned/utils'))) {
 modules.set('./'+name.replace(/\.ts$/,''),fs.readFileSync(path.join(v2,'fixtures/pinned/utils',name),'utf8'));
}
modules.set('./vendors/type-hasher',modules.get('./type-hasher'));
modules.set('original',fs.readFileSync(path.join(v2,'fixtures/pinned/original/src/search.tsx'),'utf8'));
const calls=[], toasts=[], cache = new Map(); let queue=[];
class Cache {
 constructor({namespace}={}) {this.namespace=namespace;this.listeners=new Set();}
 get=(key)=>cache.get(this.namespace+':'+key);
 set=(key,value)=>{cache.set(this.namespace+':'+key,value);this.listeners.forEach(fn=>fn());};
 subscribe=(fn)=>{this.listeners.add(fn);return ()=>this.listeners.delete(fn);};
}
function component(name) {return props=>React.createElement(name,props,props.children);}
const List=component('List');List.Item=component('List.Item');List.Item.Detail=component('List.Item.Detail');
const api={List,Action:component('Action'),ActionPanel:component('ActionPanel'),Icon:{AppWindowSidebarLeft:'sidebar'},Cache,environment:{launchType:'UserInitiated',assetsPath:'/OWNED/fixtures',isDevelopment:true},LaunchType:{Background:'Background'},Toast:{Style:{Failure:'Failure'}},showToast:async o=>{toasts.push(o);return{hide(){}};},Clipboard:{copy(){throw Error('Unexpected Clipboard producer');}},open(){throw Error('Unexpected browser producer');}};
const fetched=async (url,options)=>{
 const call={raw:String(url),url:new URL(url).href,signal:options?.signal};calls.push(call);
 const response=queue.shift(); assert.ok(response,'Every request must have an explicit owned reply');
 if(response.promise)return response.promise;
 if(response.error)throw response.error;
 return new Response(JSON.stringify(response.body??[]),{status:response.status??200,headers:{'content-type':response.type??'application/json'}});
};
const loaded=new Map();
function load(name){
 if(loaded.has(name))return loaded.get(name).exports;
 const source=modules.get(name);assert.ok(source,'Closed module map rejects '+name);
 const module={exports:{}};loaded.set(name,module);
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 const req=(id)=>{
  if(id==='react')return React;
  if(id==='@raycast/api')return api;
  if(id==='@raycast/utils')return {useFetch:load('./useFetch').useFetch};
  if(id==='dequal/lite')return require('./node_modules/dequal/lite');
  if(id==='node:crypto')return {createHash:crypto.createHash};
  if(id==='node:fs')return {readFileSync:()=>JSON.stringify({name:'onelook-thesaurus',title:'OneLook Thesaurus',author:'almatkai'})};
  if(id==='node:path')return {join:path.posix.join};
  if(id.startsWith('./'))return load(id);
  throw Error('Forbidden import '+id);
 };
 const context=vm.createContext({exports:module.exports,module,require:req,React,URL,URLSearchParams,Request,Response,Headers,AbortController,AbortSignal,Error,Buffer,Symbol,Date,Map,Set,WeakMap,WeakSet,Uint8Array,ArrayBuffer,console:{error(){},warn(){},log(){}},fetch:fetched,structuredClone, setTimeout(){throw Error('Unexpected timer');}, clearTimeout(){}} ,{codeGeneration:{strings:false,wasm:false}});
 new vm.Script(code,{filename:'PINNED/'+name}).runInContext(context,{timeout:2000});
 return module.exports;
}
const Command=load('original').default;
const vectors=['happy','a b  c','?a*','hot&max=2','a+b','%20','a#ignored',' café 😀','\ta\nb\rc','x\u0000y',"O'Reilly",' ', 'alpha=beta?x/y'];
const words=[{word:'zebra',defs:['n\tfirst','prefix adj\tsecond n\tthird'],score:1},{word:'alpha',defs:['é\tnon-ASCII','_1\tunder'],score:999},{word:'missing'},{word:'null',defs:null},{word:'empty',defs:[]},{word:'blank',defs:['','v\ttail']}];
let renderer;
const settle=async fn=>act(async()=>{await fn?.();await Promise.resolve();});
const list=()=>renderer.root.findByType('List');
const rows=()=>renderer.root.findAllByType('List.Item');
(async()=>{
 await settle(()=>{renderer=create(React.createElement(Command));});
 assert.equal(calls.length,0); assert.equal(list().props.isLoading,false);
 const oracle={schema:1,source:'3557a2ccd50cd3b4c3153afed9e4ec8c78106782',utils:'2.3.0',vectors:[],words:[]};
 for(const query of vectors){queue.push({body:words});await settle(()=>list().props.onSearchTextChange(query));assert.deepEqual(rows().map(r=>r.props.title),words.map(w=>w.word));oracle.vectors.push({query,raw:calls.at(-1).raw,url:calls.at(-1).url});}
 oracle.mime=['application/json','application/json; charset=utf-8','text/json','application/problem+json','application/vnd.json-test','application/notjson','text/html','invalid','APPLICATION/JSON','application/jsonp','text/x-json','application/json+other','application/json_extra'].map(value=>({value,isJSON:load('./fetch-utils').isJSON(value)}));
 oracle.words=rows().map((r,i)=>({input:words[i],title:r.props.title,subtitle:r.props.subtitle??null,markdown:r.props.detail.props.markdown}));
 assert.equal(list().props.isShowingDetail,false);
 await settle(()=>rows()[0].props.actions.props.children.props.onAction());assert.equal(list().props.isShowingDetail,true);
 await settle(()=>rows()[0].props.actions.props.children.props.onAction());assert.equal(list().props.isShowingDetail,false);
 const count=calls.length;await settle(()=>list().props.onSearchTextChange(''));assert.equal(calls.length,count);assert.equal(rows().length,0);
 // Actual useFetch/useCachedPromise: cached A survives its own failed revalidation;
 // an uncached B must not display A. Errors expose the original manual retry.
 queue.push({body:[{word:'cached-A',defs:['n\tA']}]});await settle(()=>list().props.onSearchTextChange('A'));
 let resolve;queue.push({promise:new Promise(r=>resolve=r)});await settle(()=>list().props.onSearchTextChange('B'));assert.equal(rows().length,0);
 queue.push({body:[{word:'new-A'}]});await settle(()=>list().props.onSearchTextChange('A'));assert.equal(rows()[0].props.title,'new-A');
 await settle(()=>resolve(new Response('[{"word":"late-B"}]',{headers:{'content-type':'application/json'}})));assert.equal(rows()[0].props.title,'new-A');
 queue.push({status:503});await settle(()=>list().props.onSearchTextChange('failure'));assert.equal(rows().length,0);assert.equal(toasts.at(-1).primaryAction.title,'Retry');
 queue.push({body:[{word:'retry-result'}]});await settle(()=>toasts.at(-1).primaryAction.onAction({hide(){}}));assert.equal(rows()[0].props.title,'retry-result');
 await settle(()=>list().props.onSearchTextChange(''));queue.push({status:500});await settle(()=>list().props.onSearchTextChange('A'));assert.equal(rows()[0].props.title,'new-A');
 await settle(()=>renderer.unmount());assert.equal(queue.length,0);
 oracle.checks={emptyLaunch:true,exactRawURL:true,responseOrder:true,metadata:true,toggle:true,emptyClears:true,cacheScope:true,lateFetchABA:true,manualRetry:true,cachedFailure:true};
 fs.writeFileSync(path.join(v2,'fixtures/source-oracles.json'),JSON.stringify(oracle,null,2)+'\n');
 console.log('SOURCE ORACLE: 13 URL cases, 6 rows, 10 behavior checks passed; all producers owned');
})().catch(e=>{console.error(e);process.exitCode=1;});
