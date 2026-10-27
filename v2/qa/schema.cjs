const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const Ajv=require('./node_modules/ajv/dist/2020'),formats=require('./node_modules/ajv-formats');
const V=path.resolve(__dirname,'..'),schema=JSON.parse(fs.readFileSync(path.join(V,'fixtures/pinned/host/schemas/extension-v3.schema.json')));
const ajv=new Ajv({allErrors:true,strict:false});formats(ajv);const validate=ajv.compile(schema);
const manifest=JSON.parse(fs.readFileSync(process.argv[2] || path.join(V,'extension.json')));assert.ok(validate(manifest),JSON.stringify(validate.errors));
const bad=[m=>m.schemaVersion=2,m=>m.runtime='javascript',m=>m.execution='tauri',m=>m.protocolVersion=2,m=>m.id='com.tezbar.bad',m=>m.preferences={},m=>m.commands=[],m=>m.commands[0].runtime='node',m=>m.commands[0].platforms=['macos'],m=>m.commands[0].concurrency='parallel',m=>m.commands[0].refreshMs=1,m=>m.commands[0].timeoutMs=999999,m=>m.capabilities=['fetch.anywhere'],m=>m.artifacts={'linux':{}},m=>m.files={'../evil':'0'.repeat(64)},m=>m.files={'bin/x':'bad'},m=>m.unknown=true,m=>m.repository='not a URI',m=>m.replaces=[],m=>m.replaces.push(m.replaces[0]),m=>m.artifacts={'aarch64-apple-darwin':{url:'http://example.invalid/a',sha256:'0'.repeat(64),executable:'bin/a',executableSha256:'0'.repeat(64)}}];
for(const mutate of bad){const m=structuredClone(manifest);mutate(m);assert.equal(validate(m),false);}
if (!process.argv[2]) fs.writeFileSync(path.join(V,'evidence/schema.json'),JSON.stringify({schemaRevision:'ea100cee3f69711de12485ba061950c5fc65258f',fullDraft202012:true,valid:1,negative:bad.length},null,2)+'\n');
console.log('SCHEMA: source manifest valid,',bad.length,'negative cases rejected by full pinned schema');
