"""Atomic completion markers, code identity and integrity-checked resume."""
from pathlib import Path
import hashlib,json,os,tempfile,time,sys
import numpy as np
from .config import Config
from .typology import generate
from .simulation import simulate
from .interventions import paired
from .structural import select

def clean(x):
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,float) and not np.isfinite(x):raise ValueError('Nonfinite research output; refusing a completion marker')
    return x

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.tmp-')
    try:
        with os.fdopen(fd,'w') as f:json.dump(clean(value),f,allow_nan=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def code_hash():
    h=hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob('*.py')):h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()


def cached_benchmark(world,starts,root):
    import fcntl
    from .benchmarks import optimize
    key=hashlib.sha256((world.hash+str(starts)+digest(Path(__file__).parent/'benchmarks.py')+digest(Path(__file__).parent/'world.py')+digest(Path(__file__).parent/'fast.py')).encode()).hexdigest()
    directory=Path(root)/'_benchmarks';directory.mkdir(parents=True,exist_ok=True);path=directory/(key+'.json')
    with (directory/(key+'.lock')).open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():return json.loads(path.read_text())
        result=optimize(world,starts,seed=int(world.hash[:8],16));atomic(path,result);return result

def run_job(job,root):
    path=Path(root)/'runs'/job['id'];identity=hashlib.sha256(json.dumps(dict(job=job,code=code_hash()),sort_keys=True).encode()).hexdigest();marker=path/'complete.json'
    if marker.exists():
        saved=json.loads(marker.read_text())
        if saved['identity']!=identity:raise ValueError(f'Code or job changed: {path}; choose a new output directory.')
        if all((path/k).exists() and digest(path/k)==v for k,v in saved['checksums'].items()):return dict(id=job['id'],status='reused')
        raise ValueError(f'Integrity check failed: {path}')
    manifest=path/'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text())['identity']!=identity:raise ValueError(f'Incomplete run has different identity: {path}')
    atomic(manifest,dict(identity=identity,code_hash=code_hash(),job=job,python=sys.version,numpy=np.__version__,scipy=__import__('scipy').__version__))
    start=time.perf_counter();world=generate(**job['world']);cfg=Config(**job['config']);kind=job.get('kind','simulation')
    if job.get('process_edits'):
        from .structural import apply
        for code in job['process_edits']:
            if code not in ('U3','U4','U5','U6'):raise ValueError('Only process edits transfer to fresh worlds')
            world,cfg=apply(world,cfg,code,[0.]*world.n)
    if kind=='paired':result=paired(world,cfg,job['intervention'],job['seed'],job['pre'],job['post'],pin=job.get('pin',False))
    elif kind=='structural':result=select(world,cfg,job['seed'],policy=job['policy'])
    elif kind=='independent':
        from .controls import independent
        result=independent(world,cfg,job['seed'])
    else:result=simulate(world,cfg,job['seed'],benchmark=cached_benchmark(world,cfg.multistarts,root))
    atomic(path/'result.json',result)
    if 'summary' in result:atomic(path/'summary.json',result['summary'])
    if 'periods' in result:
        try:
            import pyarrow as pa,pyarrow.parquet as pq
            flat=[{k:json.dumps(clean(v)) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in result['periods']]
            pq.write_table(pa.Table.from_pylist(flat),path/'periods.parquet')
        except ImportError:pass
    checksums={p.name:digest(p) for p in path.iterdir() if p.name in ('result.json','summary.json','manifest.json','periods.parquet')}
    atomic(marker,dict(identity=identity,seconds=time.perf_counter()-start,checksums=checksums))
    return dict(id=job['id'],status='completed',seconds=time.perf_counter()-start)
