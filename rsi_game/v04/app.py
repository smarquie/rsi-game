"""Interactive v0.4 sandbox on port 8766; v0.1 remains available on its own port."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from dataclasses import asdict
import argparse
import errno
import json
import threading
import time
import webbrowser
from .world import make_world
from .config import Config
from .simulation import simulate
from .storage import cache_provider

ROOT=Path(__file__).resolve().parents[2]
LOCK=threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def send(self,status,body,kind='application/json'):
        if not isinstance(body,bytes):body=body.encode()
        self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/':return self.send(200,(Path(__file__).parent/'lab.html').read_bytes(),'text/html')
        if self.path=='/report':
            report=ROOT/'results/v04/smoke/report.html'
            return self.send(200,report.read_bytes(),'text/html') if report.exists() else self.send(404,'{"error":"Generate the smoke report first"}')
        if self.path.startswith('/research/'):
            from urllib.parse import unquote,urlsplit
            base=(ROOT/'results/v04/smoke/research').resolve()
            target=(base/unquote(urlsplit(self.path).path[len('/research/'):])).resolve()
            if target.is_relative_to(base) and target.is_file():
                kind={'.html':'text/html','.json':'application/json','.csv':'text/csv','.md':'text/plain','.svg':'image/svg+xml','.png':'image/png'}.get(target.suffix,'application/octet-stream')
                return self.send(200,target.read_bytes(),kind)
        return self.send(404,'{}')
    def do_POST(self):
        if self.path!='/simulate':return self.send(404,'{}')
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.headers.get("Host")}':return self.send(403,'{}')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send(415,'{}')
        if not LOCK.acquire(False):return self.send(409,'{"error":"A run is already in progress"}')
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<4096:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(length));periods=int(data.get('periods',60));seed=int(data.get('seed',0))
            if not 0<=periods<=300 or not 0<=seed<2**32:raise ValueError('Periods must be 0–300; seed must be an unsigned 32-bit integer')
            world=make_world(data.get('scenario','frustrated'),seed=seed,alpha_max=float(data.get('alpha',.3)),budget_factor=float(data.get('budget',1)))
            config=Config(periods=periods,k=min(int(data.get('k',1)),world.n),beta=float(data.get('beta',.7)),w_min=float(data.get('width',.1)),
                a_max=float(data.get('amplitude',.08)),within_period=data.get('regime','fixed'),frequencies=data.get('frequencies','nonresonant'),multistarts=16)
            start=time.perf_counter();result=simulate(world,config,seed,cache_provider(ROOT/'results/v04/_lab_benchmarks',16))
            return self.send(200,json.dumps(dict(result=result,config=asdict(config),world=world.to_dict(),seconds=time.perf_counter()-start),allow_nan=False))
        except (ValueError,TypeError,KeyError) as error:return self.send(400,json.dumps(dict(error=str(error))))
        finally:LOCK.release()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    url=f'http://127.0.0.1:{args.port}'
    try:server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    except OSError as error:
        if error.errno!=errno.EADDRINUSE:raise
        from urllib.request import urlopen
        with urlopen(url,timeout=2) as response:page=response.read(1024).decode()
        if '<title>RSI Functions v0.4 · Lab</title>' not in page:raise RuntimeError('Port belongs to another app; choose a different --port') from error
        print(f'v0.4 lab already running: {url}',flush=True)
        if not args.no_browser:webbrowser.open(url)
        return
    print(f'RSI Functions v0.4: {url} (Ctrl-C to stop)',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
