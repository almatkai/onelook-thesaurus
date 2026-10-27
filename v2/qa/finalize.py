"""Prepare review hashes only. Never stages, commits, pushes or deletes a clone."""
import sys
sys.dont_write_bytecode=True
import json,pathlib,subprocess,hashlib,os
from env import V2,QA
repo=V2.parent;expected='3557a2ccd50cd3b4c3153afed9e4ec8c78106782'
def git(*args):return subprocess.check_output(['git',*args],cwd=repo)
assert git('rev-parse','--show-toplevel').decode().strip()==str(repo)
assert git('branch','--show-current').decode().strip()=='feat/native-v2-rust'
assert git('rev-parse','HEAD').decode().strip()==expected
assert git('diff','--cached','--name-only')==b'','Index must remain empty'
gates=json.loads((V2/'evidence/gates.json').read_text());assert gates['failed']==0 and len(gates['gates'])==23
assert all(r['state']=='passed' or r['name'].startswith('windows-') and r['state']=='blocked' for r in gates['gates'])
process=json.loads((V2/'evidence/process.json').read_text());assert process['count']>=32 and process['canceledOpens']==140
pack=json.loads((V2/'evidence/development-package.json').read_text());assert pack['extractedProductionChecks']==10
zip_path=V2/pack['archive'];assert hashlib.sha256(zip_path.read_bytes()).hexdigest()==pack['sha256']
tracked=git('ls-files','-z','--cached','--others','--exclude-standard').decode().split('\0')
paths=sorted({p for p in tracked if p and (p=='README.md' or p.startswith('v2/')) and p!='v2/evidence/review-inventory.json'})
for p in paths:
 assert not any(s in p.split('/') for s in ['node_modules','target','.qa','dist','__pycache__']),p
 assert not pathlib.Path(repo/p).is_symlink(),p
 assert not p.endswith(('.zip','.pyc')),p
inventory={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths}
review={'root':str(repo),'branch':'feat/native-v2-rust','head':expected,'stagedFiles':0,'scope':'README.md and all Git-visible v2 files; excludes this inventory itself','files':inventory,'parentInstruction':'Before commit, compare each STAGED blob (git show :path) SHA256 with this inventory, and compare the entire staged path set; exclude this inventory from its self-hash comparison.'}
(V2/'evidence/review-inventory.json').write_text(json.dumps(review,indent=2)+'\n')
print('REVIEW READY:',len(paths),'files hashed;',gates['passed'],'passed gates,',gates['blocked'],'Windows toolchain-blocked; index empty')
print('root:',repo,'branch: feat/native-v2-rust HEAD:',expected)
print(git('status','--short').decode(),end='')
