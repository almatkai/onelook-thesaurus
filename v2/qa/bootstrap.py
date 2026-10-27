"""Install only locked QA dependencies into ignored owned directories.
No compiler, target, fonts, global packages, host or SDK mutations.
"""
import sys
sys.dont_write_bytecode=True
import pathlib,subprocess,shutil
from env import V2,QA,env
source=QA/'v1';source.mkdir(exist_ok=True)
for path in subprocess.check_output(['git','ls-tree','-r','--name-only','3557a2ccd50cd3b4c3153afed9e4ec8c78106782'],cwd=V2.parent,text=True).splitlines():
 p=source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show','3557a2ccd50cd3b4c3153afed9e4ec8c78106782:'+path],cwd=V2.parent))
for folder,manifest in [(source,source),(QA/'deps',V2/'qa')]:
 folder.mkdir(exist_ok=True)
 if folder!=manifest:
  for n in ['package.json','package-lock.json']:shutil.copyfile(manifest/n,folder/n)
 subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=folder,env=env(),check=True)
link=V2/'qa/node_modules'
if not link.exists():link.symlink_to('../.qa/deps/node_modules',target_is_directory=True)
print('QA dependencies and unchanged V1 copy are isolated under v2/.qa')
