"""Real SDK JSONL pipes and owned TLS transport. No live Datamuse/OS producers."""
import sys
sys.dont_write_bytecode=True
import pathlib,json,subprocess,threading,queue,ssl,http.server,uuid,time,urllib.parse,hashlib,os
from env import V2,QA,env
ID='com.tezbar.native.onelook-thesaurus'
class Peer:
 def __init__(self,exe,args=(),data='process-data'):
  self.frames=queue.Queue();self.pending={};self.stderr=open(QA/(data+'.stderr'),'wb');self.data=QA/data;self.data.mkdir(parents=True,exist_ok=True)
  self.p=subprocess.Popen([str(exe),*map(str,args)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,env=env())
  def read():
   for line in self.p.stdout:
    assert len(line)<=16*1024*1024+1
    self.frames.put(json.loads(line))
   self.frames.put(None)
  self.reader=threading.Thread(target=read,daemon=True);self.reader.start();self.hello=self.get();assert self.hello['id']==ID and self.hello['sdkVersion']=='0.1.1'
 def send(self,obj):self.p.stdin.write(json.dumps(obj,separators=(',',':')).encode()+b'\n');self.p.stdin.flush()
 def get(self):
  f=self.frames.get(timeout=20);assert f is not None,'Unexpected EOF';assert f['type']!='request','Port must not invoke host/OS producers';return f
 def request(self,method,params):
  i='h:'+str(uuid.uuid4());self.send({'type':'request','id':i,'method':method,'params':params});return i
 def reply(self,i):
  if i in self.pending:return self.pending.pop(i)
  while True:
   f=self.get()
   if f.get('id')==i:return f
   self.pending[f.get('id')]=f
 def call(self,m,p):return self.reply(self.request(m,p))
 def init(self):assert self.call('initialize',{'protocol':1,'extensionId':ID,'platform':'macOS','packageDir':str(V2),'dataDir':str(self.data),'tempDir':str(QA/'tmp'),'grantedCapabilities':[]})['result']['ready']
 def open(self,s,q=''):return self.call('session.open',{'sessionId':s,'commandName':'search','searchText':q})
 def search(self,s,q):return self.call('session.call',{'sessionId':s,'operation':'extension:search-text-changed','payload':{'searchText':q}})
 def action(self,s,a):return self.call('session.call',{'sessionId':s,'operation':'extension:invoke-action','payload':{'actionId':a}})
 def close(self):
  if self.p.poll() is None:
   self.p.stdin.close()
   try:self.p.wait(timeout=5)
   except subprocess.TimeoutExpired:self.p.kill();self.p.wait();raise
  self.reader.join(timeout=2);self.stderr.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

def rows(reply):return [n for n in reply['result']['root'].get('children',[]) if n['type']=='List.Item']
def action(reply,title):return next(a['id'] for a in reply['result']['actions'] if a['title']==title)
class Handler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.0'
 def log_message(self,*args):pass
 def do_GET(self):
  q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query,keep_blank_values=True).get('ml',[''])[0]
  server.paths.append(self.path)
  server.counts[q]=server.counts.get(q,0)+1
  server.seen.put((q,self.path))
  if q.startswith('hold'):
   gate=server.gates.setdefault(q,threading.Event());gate.wait(12)
  if q=='cached' and server.counts[q]>1:self.respond(503,b'');return
  if q=='status':self.respond(503,b'PRIVATE SERVICE FAILURE','text/plain');return
  if q=='redirect':self.respond(302,b'',location='https://api.datamuse.com/words?ml=NEVER');return
  if q=='html':self.respond(200,b'<script>throw 1</script>','text/html');return
  if q=='bad':self.respond(200,b'[{"word":3}]');return
  if q=='big':self.respond(200,b' '*(512*1024+1));return
  if q=='rows':self.respond(200,json.dumps([{'word':str(i)} for i in range(1001)]).encode());return
  if q=='chunked':
   self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Transfer-Encoding','chunked');self.end_headers()
   try:
    for _ in range(130):self.wfile.write(b'1000\r\n'+b' '*4096+b'\r\n');self.wfile.flush()
    self.wfile.write(b'0\r\n\r\n')
   except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
   return
  if q=='retry' and not server.retry:server.retry=True;self.respond(503,b'');return
  words=[] if q=='empty' else [{'word':q+'-z','defs':['n\tfirst','adj\tsecond n\tthird'],'score':1},{'word':q+'-a','score':999},{'word':q+'-z','defs':[]}]
  self.respond(200,json.dumps(words,ensure_ascii=False).encode())
 def respond(self,status,body,ctype='application/json',location=None):
  try:
   self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
   if location:self.send_header('Location',location)
   self.end_headers();self.wfile.write(body);self.wfile.flush()
  except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass

def seen(q):
 while True:
  got,path=server.seen.get(timeout=8)
  if got==q:return path

def production(exe,label):
 with Peer(exe,data=label) as p:
  p.init();r=p.open('s',None);assert rows(r)==[] and r['result']['refreshMs'] is None
  r=p.search('s','x'*4097);assert '4096' in r['result']['message'] and 'searchText' not in r['result']['root']['props']
  assert rows(p.search('s',''))==[]
  assert p.action('s','old')['result']['mode']=='unchanged'
  assert p.call('session.dispose',{'sessionId':'s'})['result']=={}
  assert 'error' in p.search('s','')
 return 6

if __name__=='__main__':
 certs=QA/'tls';certs.mkdir(parents=True,exist_ok=True)
 config=certs/'openssl.cnf';config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=owned-onelook-qa\n[ext]\nsubjectAltName=IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-config',str(config),'-keyout',str(certs/'key.pem'),'-out',str(certs/'cert.pem')],env=env(),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;server.seen=queue.Queue();server.gates={};server.retry=False;server.paths=[];server.counts={}
 tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(certs/'cert.pem',certs/'key.pem');server.socket=tls.wrap_socket(server.socket,server_side=True)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();endpoint=f'https://127.0.0.1:{server.server_port}'
 checks=[]
 try:
  exe=V2/'target/1.85.0/debug/onelook-qa'
  with Peer(exe,[endpoint,certs/'cert.pem']) as p:
   p.init();r=p.open('s');assert rows(r)==[];assert server.seen.empty();checks.append('empty launch: no HTTP/no reverse RPC')
   r=p.search('s','order');assert [x['props']['title'] for x in rows(r)]==['order-z','order-a','order-z'];assert 'detail' not in rows(r)[0]['props'];checks.append('service order, duplicates, subtitle, hidden definitions')
   toggle=action(r,'Toggle Definitions');r=p.action('s',toggle);assert rows(r)[0]['props']['detail']['props']['markdown']=='# order-z\n---\n`n` first\n\n`adj` second n\tthird'
   assert p.action('s',toggle)['result']['mode']=='unchanged';assert action(r,'Toggle Definitions')!=toggle;checks.append('toggle action consumption and fresh repeat token')
   p.open('other');assert p.action('other',action(r,'Toggle Definitions'))['result']['mode']=='unchanged';checks.append('cross-session token inert')
   for q in ['status','html','bad','big','rows','chunked','redirect']:
    r=p.search('s',q);assert r['result']['message'];assert rows(r)==[];assert 'PRIVATE' not in r['result']['message'];assert action(r,'Retry');checks.append('bounded sanitized failure '+q)
   r=p.search('s','retry');token=action(r,'Retry');r=p.action('s',token);assert rows(r)[0]['props']['title']=='retry-z';assert p.action('s',token)['result']['mode']=='unchanged';checks.append('manual retry consumed before await')
   old=r['result']['actions'][0]['id'];p.search('s',None);assert p.action('s',old)['result']['mode']=='unchanged';p.search('s','');checks.append('invalid intermediate revokes action and results')
   oracle=json.loads((V2/'fixtures/source-oracles.json').read_text())
   for q in ['a b  c','hot&max=2','a#ignored',' café 😀','\ta\nb\rc']:
    p.search('s',q)
    expected=next(v['url'] for v in oracle['vectors'] if v['query']==q)
    u=urllib.parse.urlsplit(expected);assert server.paths[-1]==u.path+'?'+u.query
    checks.append('actual URL route/encoding '+repr(q))
   p.search('s','cached');r=p.search('s','cached');assert rows(r)[0]['props']['title']=='cached-z' and 'HTTP 503' in r['result']['message'];checks.append('same-query cached results survive failed revalidation')

   # Slow A, B, A; SDK reader cancels old HTTP future and cloned-state commits.
   slow=p.request('session.call',{'sessionId':'s','operation':'extension:search-text-changed','payload':{'searchText':'hold-A'}});seen('hold-A')
   mid=p.request('session.call',{'sessionId':'s','operation':'extension:search-text-changed','payload':{'searchText':'B'}})
   last=p.request('session.call',{'sessionId':'s','operation':'extension:search-text-changed','payload':{'searchText':'A'}})
   assert rows(p.reply(last))[0]['props']['title']=='A-z';assert 'error' in p.reply(slow);p.reply(mid);server.gates['hold-A'].set();checks.append('reader-order A/B/A cancellation')
   # Retry already in flight, then draft changes. It may finish read-only; queued
   # current search wins. Renderer prerequisite separately fences its old view.
   r=p.search('s','status');retry=action(r,'Retry');rid=p.request('session.call',{'sessionId':'s','operation':'extension:invoke-action','payload':{'actionId':retry}});p.search('s','after-retry');p.reply(rid);assert p.action('s',retry)['result']['mode']=='unchanged';checks.append('queued retry token never reacquired')
   pending=p.request('session.call',{'sessionId':'other','operation':'extension:search-text-changed','payload':{'searchText':'hold-dispose'}});seen('hold-dispose')
   p.call('session.dispose',{'sessionId':'other'});assert 'error' in p.reply(pending);server.gates['hold-dispose'].set();assert 'result' in p.open('other-new');checks.append('dispose cancels owned HTTP; late response cannot revive session')
   p.send({'type':'cancel','requestId':rid,'reason':'late completed action cancellation'});assert p.action('s','stale')['result']['mode']=='unchanged';checks.append('late cancellation does not mutate completed/current session')
   # Cancellation can drop open without calling adapter dispose. Exercise >128.
   for i in range(140):
    q='hold-open-'+str(i);sid='canceled-'+str(i)
    rid=p.request('session.open',{'sessionId':sid,'commandName':'search','searchText':q});seen(q)
    p.send({'type':'cancel','requestId':rid,'reason':'owned QA cancel'})
    assert 'error' in p.reply(rid);server.gates[q].set()
   assert rows(p.open('after140'))==[];checks.append('140 canceled opens release SDK and adapter capacity')
   # 128 includes s/other/after140. At 129 SDK must reject, then disposal frees.
   for i in range(125):assert 'result' in p.open('capacity-'+str(i))
   assert 'error' in p.open('over-capacity')
   p.call('session.dispose',{'sessionId':'capacity-0'});assert 'result' in p.open('replacement');checks.append('128 session capacity and recovery')
   p.send({'type':'response','id':'e:'+str(uuid.uuid4()),'result':{'ok':True}});assert p.action('s','unknown')['result']['mode']=='unchanged';checks.append('late reverse response inert; no reverse calls used')
   cachefile=p.data/'datamuse-cache-v1.json';assert cachefile.stat().st_size<=2*1024*1024;cache=json.loads(cachefile.read_text());assert len(cache)<=8;checks.append('bounded cache file, full-key entries')
  checks.append('EOF bounded shutdown')
  # Exactly-16MiB accepted and over-limit rejected by real pinned SDK framing.
  for extra in [0,1]:
   with Peer(exe,[endpoint,certs/'cert.pem'],data='frame-'+str(extra)) as p:
    p.init();base={'type':'request','id':'h:'+str(uuid.uuid4()),'method':'unknown','params':{'padding':''}};raw=json.dumps(base,separators=(',',':')).encode();base['params']['padding']='x'*(16*1024*1024-len(raw)+extra);p.send(base)
    if extra:assert p.p.wait(timeout=5)!=0
    else:assert 'error' in p.get()
   checks.append('16MiB '+('overflow rejection' if extra else 'exact boundary'))
  for c in range(2):
   count=production(V2/'target/1.85.0/debug/onelook-thesaurus','production-'+str(c));checks.append(f'actual production process no-network: {count} checks')
  (V2/'evidence/process.json').write_text(json.dumps({'checks':checks,'count':len(checks),'canceledOpens':140,'realSDK':True,'ownedTLS':True,'liveProviderCalls':0,'reverseProducers':0},indent=2)+'\n')
  print('PROCESS QA:',len(checks),'checks; 140 canceled opens; real SDK pipes and owned TLS; zero live provider/OS calls')
 finally:
  for gate in server.gates.values():gate.set()
  server.shutdown();server.server_close();thread.join(timeout=2)
