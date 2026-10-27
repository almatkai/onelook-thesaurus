"""Copy authentic grant files from locked, isolated dependency sources."""
import sys
sys.dont_write_bytecode=True
import json,pathlib,hashlib,re,shutil
from env import V2,QA
metadata=json.loads((QA/'cargo-metadata.json').read_text());records=[]
for pkg in metadata['packages']:
 if pkg['name']=='tezbar-onelook-thesaurus':continue
 root=pathlib.Path(pkg['manifest_path']).parent;dest=V2/'notices/cargo'/(pkg['name']+'-'+pkg['version']);grants=[]
 for p in sorted(root.rglob('*')):
  if p.is_file() and re.search(r'^(licen[cs]e|copying|copyright|notice|authors)([._-]|$)',p.name,re.I) and '.git' not in p.parts:
   rel=p.relative_to(root);out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);data=p.read_bytes();out.write_bytes(data);grants.append({'path':str(out.relative_to(V2)),'source':str(rel),'sha256':hashlib.sha256(data).hexdigest()})
 records.append({'name':pkg['name'],'version':pkg['version'],'licenseExpression':pkg['license'],'source':pkg['source'],'rustVersion':pkg.get('rust_version'),'grants':grants,'missingGrantFiles':not bool(grants)})
# QA dependencies are absent from the Rust runtime/package. Preserve their own
# supplied grants plus package metadata, rather than synthesizing license text.
for base,group in [(QA/'deps/node_modules','qa-npm'),(QA/'v1/node_modules','v1-npm')]:
 names=json.loads((V2/'qa/package-lock.json').read_text())['packages'] if group=='qa-npm' else {'node_modules/@raycast/utils':{},'node_modules/@raycast/api':{}}
 for key in names:
  if not key.startswith('node_modules/'):continue
  root=base/key.removeprefix('node_modules/');data=json.loads((root/'package.json').read_text());dest=V2/'notices'/group/(data['name'].replace('/','-').replace('@','')+'-'+data['version']);dest.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/'package.json',dest/'package.json');grants=[]
  for p in root.iterdir():
   if p.is_file() and re.search(r'^(licen[cs]e|copying|copyright|notice|authors)([._-]|$)',p.name,re.I):
    b=p.read_bytes();out=dest/p.name;out.write_bytes(b);grants.append({'path':str(out.relative_to(V2)),'source':p.name,'sha256':hashlib.sha256(b).hexdigest()})
  records.append({'name':data['name'],'version':data['version'],'licenseExpression':data.get('license'),'source':group,'grants':grants,'missingGrantFiles':not bool(grants)})
(V2/'notices/inventory.json').write_text(json.dumps(records,indent=2)+'\n')
print('dependency packages',len(records),'copied grants',sum(len(r['grants']) for r in records),'missing grant files',[(r['name'],r['version']) for r in records if r['missingGrantFiles']])
