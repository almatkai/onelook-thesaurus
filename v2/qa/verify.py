"""Finite reproducible gates. All logs/caches/output remain under this v2 tree."""
import sys
sys.dont_write_bytecode=True
import json,subprocess,pathlib,hashlib,shutil
from env import V2,QA,env
results=[]
def run(name,args,tool='stable',cwd=V2,allowed=False,custom=None):
 log=QA/(name+'.log')
 with log.open('w') as f:p=subprocess.run(args,cwd=cwd,env=custom or env(tool),stdout=f,stderr=subprocess.STDOUT)
 results.append({'name':name,'command':args,'toolchain':tool,'exit':p.returncode,'state':'passed' if p.returncode==0 else 'blocked' if allowed else 'failed','logSha256':hashlib.sha256(log.read_bytes()).hexdigest()})
 print(name,results[-1]['state'],flush=True)
 if p.returncode and not allowed:raise RuntimeError(name+' failed; inspect '+str(log))
if __name__=='__main__':
 try:
  run('source-oracle',['node','qa/source-oracle.cjs'])
  run('renderer-patch',['python3','qa/prepare-host-patch.py'])
  run('renderer',['node','qa/renderer.cjs'])
  run('schema',['node','qa/schema.cjs'])
  for tool in ['1.85.0','stable']:
   run('fmt-'+tool,['cargo','fmt','--check'],tool)
   run('tests-'+tool,['cargo','test','--locked','--all-targets','--all-features'],tool)
   run('clippy-'+tool,['cargo','clippy','--locked','--all-targets','--all-features','--','-D','warnings'],tool)
   run('windows-check-'+tool,['cargo','check','--locked','--all-targets','--all-features','--target','x86_64-pc-windows-gnu'],tool,allowed=True)
   run('windows-clippy-'+tool,['cargo','clippy','--locked','--all-targets','--all-features','--target','x86_64-pc-windows-gnu','--','-D','warnings'],tool,allowed=True)
  run('qa-build',['cargo','build','--locked','--bins','--all-features'],'1.85.0')
  run('process',['python3','qa/process.py'])
  run('v1-test',['npm','test'],cwd=QA/'v1')
  run('v1-typecheck',['npm','run','typecheck'],cwd=QA/'v1')
  run('metadata',['cargo','metadata','--locked','--format-version','1'],'1.85.0')
  shutil.copyfile(QA/'metadata.log',QA/'cargo-metadata.json')
  run('notices',['python3','qa/notices.py'])
  run('pin-audit',['python3','qa/audit.py'])
  # New empty home/target per invocation. The final build is default-feature
  # production and obtains the immutable SDK via its locked HTTPS Git source.
  suffix=0
  while (QA/('final-fresh-cargo-'+str(suffix))).exists():suffix+=1
  home=QA/('final-fresh-cargo-'+str(suffix));target=V2/'target'/('final-fresh-'+str(suffix));assert not target.exists();e=env('1.85.0');e['CARGO_HOME']=str(home);e['CARGO_TARGET_DIR']=str(target);home.mkdir();target.mkdir()
  run('fresh-source-build',['cargo','build','--locked','--release','--bin','onelook-thesaurus'],'1.85.0',custom=e)
  run('package',['python3','qa/package.py',str(target/'release/onelook-thesaurus')])
 finally:
  report={'gates':results,'passed':sum(r['state']=='passed' for r in results),'blocked':sum(r['state']=='blocked' for r in results),'failed':sum(r['state']=='failed' for r in results),'windowsGaps':{'mingwCompiler':shutil.which('x86_64-w64-mingw32-gcc',path=env()['PATH']),'dlltool':shutil.which('x86_64-w64-mingw32-dlltool',path=env()['PATH']),'msvcTargetInstalled':(pathlib.Path(env()['PATH'].split(':')[0]).parent/'lib/rustlib/x86_64-pc-windows-msvc').exists(),'windowsRuntimeAndGUI':'not-run'},'hostGUI':'not-run','liveProductAPI':'not-run; zero calls in QA'}
  (V2/'evidence/gates.json').write_text(json.dumps(report,indent=2)+'\n')
