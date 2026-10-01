"""Small local laboratory. Serves only two named assets; binds to loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import asdict
import argparse
import json
import time
import threading
import webbrowser
from .params import *
from .meta import run

ROOT=Path(__file__).resolve().parent.parent
LOCK=threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def send(self,status,body,kind='application/json'):
        if isinstance(body,str): body=body.encode()
        self.send_response(status); self.send_header('Content-Type',kind+'; charset=utf-8')
        self.send_header('Content-Length',str(len(body))); self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path=='/': return self.send(200,(ROOT/'rsi_game/lab.html').read_bytes(),'text/html')
        if self.path=='/report':
            path=ROOT/'results/report.html'
            if path.exists(): return self.send(200,path.read_bytes(),'text/html')
            return self.send(404,'Generate the report with: python -m rsi_game report','text/plain')
        return self.send(404,json.dumps(dict(error='Not found')))

    def do_POST(self):
        if self.path!='/simulate': return self.send(404,'{}')
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.headers.get("Host")}': return self.send(403,'{"error":"Same-origin requests required"}')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.send(415,'{"error":"JSON required"}')
        if not LOCK.acquire(blocking=False): return self.send(409,'{"error":"A simulation is already running"}')
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<4096: raise ValueError('Invalid request size')
            options=json.loads(self.rfile.read(length)); cycles=int(options.get('cycles',40)); seed=int(options.get('seed',0))
            if not 1<=cycles<=200 or not 0<=seed<2**32: raise ValueError('Cycles must be 1–200; seed must be a 32-bit unsigned integer')
            K=options.get('K','5'); K=None if K=='inf' else int(K)
            choice=DesignerChoice(K=K,n_cycles=cycles,edit_class=int(options.get('edit_class',2)),promotion=options.get('promotion','auto'),eval_timing=options.get('eval_timing','immediate'),exact=options.get('exact','false')=='true')
            cfg=AgentConfig(); weak=options.get('weak','')
            if weak: cfg=cfg.edit('c',ROLES.index(weak),.5)
            start=time.perf_counter(); rows=run(seed,agent=cfg,designer=choice)
            return self.send(200,json.dumps(dict(rows=rows,seconds=time.perf_counter()-start,parameters=dict(seed=seed,agent=asdict(cfg),designer=asdict(choice))),allow_nan=False))
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as error:
            return self.send(400,json.dumps(dict(error=str(error))))
        finally: LOCK.release()


def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8765); p.add_argument('--no-browser',action='store_true'); args=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}'; print(f'RSI Game: {url} (Ctrl-C to stop)',flush=True)
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
