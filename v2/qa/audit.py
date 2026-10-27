"""Independent pinned input audit, separate from mutable review inventory."""
import sys
sys.dont_write_bytecode=True
import pathlib,json,hashlib,subprocess,tarfile,io,urllib.request,base64
from env import V2,QA
sha=lambda b:hashlib.sha256(b).hexdigest()
SDK='e955911f0bf5b558f9d3eb5183df0adc95c22af2';HOST='ea100cee3f69711de12485ba061950c5fc65258f';OWN='3557a2ccd50cd3b4c3153afed9e4ec8c78106782'
pins=json.loads((V2/'fixtures/pins.json').read_text());checked=0
for pin in pins:
 actual=(V2/pin['path']).read_bytes();assert sha(actual)==pin['sha256'],pin['path']
 if pin.get('url'):
  upstream=urllib.request.urlopen(pin['url'],timeout=30).read();assert upstream==actual==(V2.parent/'assets/command-icon.png').read_bytes();assert sha(actual)=='0723e3c35808ff5ff0aff5fe2dc81db4c4615b013e02d7b35406b29bb096d032'
 else:
  rev=pin['revision'];assert rev in [SDK,HOST,OWN]
  repo=V2.parent if rev==OWN else V2.parent.parent/'tezbar-extension-sdk-rust' if rev==SDK else pathlib.Path('/Users/almat/Desktop/code/Tezbar APP/Tezbar')
  assert subprocess.check_output(['git','-C',str(repo),'show',rev+':'+pin['source']])==actual,pin['path']
 checked+=1
p=json.loads((V2/'fixtures/utils-provenance.json').read_text());lock=json.loads((V2.parent/'package-lock.json').read_text());entry=lock['packages']['node_modules/@raycast/utils'];assert p['resolved']==entry['resolved'] and p['integrity']==entry['integrity']
b=urllib.request.urlopen(entry['resolved'],timeout=30).read();alg,digest=entry['integrity'].split('-',1);assert base64.b64encode(hashlib.new(alg,b).digest()).decode()==digest;assert sha(b)==p['archiveSha256'];tar=tarfile.open(fileobj=io.BytesIO(b));m=tar.extractfile(p['sourceMapMember']).read();assert sha(m)==p['sourceMapSha256'];m=json.loads(m);sources=dict(zip(m['sources'],m['sourcesContent']))
for record in p['sources']:
 b=(V2/record['path']).read_bytes();assert b==sources[record['source']].encode();assert sha(b)==record['sha256'];checked+=1
native=(V2/'fixtures/pinned/host/src-tauri/src/native_core/extensions/native.rs').read_text();start=native.index('fn annotate(');end=native.index('\nstruct LaunchCleanup',start);assert (V2/'fixtures/derived/host-annotate.rs').read_text()==native[start:end]+'\n';start=native.index('json!({"sessionId":id,"commandName":command');end=native.index(',deadline(&entry)',start);assert (V2/'fixtures/derived/host-open-payload.rs').read_text()==native[start:end]+'\n'
# All V1 tracked bytes remain exactly pinned, apart from one discovery link.
for path in subprocess.check_output(['git','ls-tree','-r','--name-only',OWN],cwd=V2.parent,text=True).splitlines():
 b=subprocess.check_output(['git','show',OWN+':'+path],cwd=V2.parent)
 if path=='README.md':assert (V2.parent/path).read_bytes()==b+b'\n\n[Standalone Rust port and verification](v2/README.md).\n'
 else:assert (V2.parent/path).read_bytes()==b,path
# Assert every package with an MSRV declaration fits the promised toolchain.
metadata=json.loads((QA/'cargo-metadata.json').read_text());too_new=[]
for pkg in metadata['packages']:
 version=pkg.get('rust_version')
 if version and tuple(map(int,version.split('.')[:2]))>(1,85):too_new.append((pkg['name'],version))
assert not too_new,too_new
report={'pinnedFilesAndLibrarySources':checked,'derivedHostFunctions':2,'V1UnchangedExceptReadme':True,'cargoPackages':len(metadata['packages']),'declaredMSRVOver185':too_new,'immutableSDK':SDK,'immutableHost':HOST,'independentNetworkInputs':['upstream original icon','SRI-verified locked utils tarball'],'liveProductAPICalls':0}
(V2/'evidence/pin-audit.json').write_text(json.dumps(report,indent=2)+'\n');print('PIN AUDIT:',checked,'pinned/source-map files, 2 actual host helpers, unchanged V1 bytes, MSRV declarations passed')
