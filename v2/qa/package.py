"""Deterministic closed-member development ZIP; does not install or publish."""
import sys
sys.dont_write_bytecode=True
import pathlib,json,hashlib,zipfile,io,subprocess,shutil,stat
from env import V2,QA,env
from process import production,Peer,rows,action
sha=lambda b:hashlib.sha256(b).hexdigest()
def validate(blob):
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  names=z.namelist();assert len(set(names))==len(names);assert len(names)<=4096
  for info in z.infolist():
   parts=pathlib.PurePosixPath(info.filename).parts
   assert not info.is_dir() and not info.filename.startswith('/') and all(p not in ['.','..'] for p in parts) and '\\' not in info.filename and ':' not in info.filename
   assert stat.S_IFMT(info.external_attr>>16)==stat.S_IFREG
  manifest=json.loads(z.read('extension.json'));files=manifest['files'];assert set(names)==set(files)|{'extension.json'}
  for name,digest in files.items():assert sha(z.read(name))==digest
  assert manifest['artifacts']=={} and all(x['state']=='not-run' for x in manifest['verification'])
  assert (z.getinfo('bin/onelook-thesaurus').external_attr>>16)&0o111
  return manifest,names
if __name__=='__main__':
 binary=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else V2/'target/final-fresh/release/onelook-thesaurus'
 files={'bin/onelook-thesaurus':binary.read_bytes(),'resources/command-icon.png':(V2/'resources/command-icon.png').read_bytes(),'LICENSE':(V2/'LICENSE').read_bytes(),'NOTICE':(V2/'NOTICE').read_bytes()}
 for p in sorted((V2/'notices').rglob('*')):
  if p.is_file():files['resources/notices/'+str(p.relative_to(V2/'notices'))]=p.read_bytes()
 manifest=json.loads((V2/'extension.json').read_text());manifest['files']={k:sha(b) for k,b in sorted(files.items())};files['extension.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
 def archive():
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
   for name,data in sorted(files.items()):
    info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|(0o755 if name.startswith('bin/') else 0o644))<<16;info.compress_type=zipfile.ZIP_STORED;z.writestr(info,data)
  return buf.getvalue()
 first=archive();assert first==archive();packaged,names=validate(first)
 dist=V2/'dist';dist.mkdir(exist_ok=True);zip_path=dist/'onelook-thesaurus-aarch64-apple-darwin-development.zip';zip_path.write_bytes(first)
 extracted=QA/'extracted-development';extracted.mkdir(exist_ok=True)
 with zipfile.ZipFile(io.BytesIO(first)) as z:
  for info in z.infolist():
   p=extracted/info.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info.filename));p.chmod((info.external_attr>>16)&0o777)
 subprocess.run(['node',str(V2/'qa/schema.cjs'),str(extracted/'extension.json')],env=env(),check=True)
 command_checks=production(extracted/'bin/onelook-thesaurus','extracted-production')
 # Exercise the extracted genuine production command through bounded, owned cache
 # data, including details/actions, without contacting the live product provider.
 data=QA/'extracted-cache';data.mkdir(exist_ok=True);(data/'datamuse-cache-v1.json').write_text(json.dumps([{'key':'https://api.datamuse.com/words?qe=ml&md=d&ml=','words':[{'word':'owned cached word','defs':['n\towned definition']}]}]))
 with Peer(extracted/'bin/onelook-thesaurus',data='extracted-cache') as p:
  p.init();r=p.open('owned-cache',None);assert rows(r)[0]['props']['title']=='owned cached word';token=action(r,'Toggle Definitions');r=p.action('owned-cache',token);assert rows(r)[0]['props']['detail']['props']['markdown']=='# owned cached word\n---\n`n` owned definition';assert p.action('owned-cache',token)['result']['mode']=='unchanged';command_checks+=3
 info=json.loads(subprocess.check_output([str(extracted/'bin/onelook-thesaurus'),'--protocol-info'],env=env()));assert info['commands']==['search'] and info['sdkVersion']=='0.1.1';command_checks+=1
 report={'archive':str(zip_path.relative_to(V2)),'sha256':sha(first),'bytes':len(first),'memberCount':len(names),'executableSha256':sha(files['bin/onelook-thesaurus']),'deterministicSameInputs':True,'exactClosedMemberMap':True,'extractedProductionChecks':command_checks,'liveProductAPICalls':0,'installed':False,'released':False,'verification':'not-run on both OS; isolated process evidence only','files':packaged['files']}
 (V2/'evidence/development-package.json').write_text(json.dumps(report,indent=2)+'\n');print('PACKAGE:',len(names),'closed members; deterministic ZIP',sha(first),';',command_checks,'extracted production checks')
