"""Atomic, resumable, content-identified research runs and shared benchmarks."""
from dataclasses import asdict
from pathlib import Path
import csv
import hashlib
import json
import os
import sys
import tempfile
import time
import numpy as np
from . import VERSION
from .config import Config
from .world import World,make_world
from .benchmarks import benchmark_bundle
from .simulation import simulate


def clean(value):
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.generic): return value.item()
    if isinstance(value,dict): return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [clean(v) for v in value]
    return value


def atomic_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(clean(value),indent=2,allow_nan=False)+'\n'
    fd,tmp=tempfile.mkstemp(prefix='.writing-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f: f.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def code_hash():
    digest=hashlib.sha256()
    for name in ('config.py','world.py','fast.py','explore.py','function_state.py','review.py','period.py','benchmarks.py','outside.py','simulation.py'):
        path=Path(__file__).parent/name;digest.update(name.encode());digest.update(path.read_bytes())
    return digest.hexdigest()[:20]


def cache_provider(directory,starts):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    def provider(world):
        # Advisory lock prevents duplicate expensive work across parallel runs.
        import fcntl
        key=f'{world.hash}_{starts}_{VERSION}'
        target=directory/(key+'.json')
        with (directory/(key+'.lock')).open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if target.exists():
                cached=json.loads(target.read_text())
                if cached.get('benchmark_code_hash')==benchmark_code_hash(): return cached['result']
            result=benchmark_bundle(world,starts)
            atomic_json(target,dict(benchmark_code_hash=benchmark_code_hash(),result=result))
            return result
    return provider


def benchmark_code_hash():
    digest=hashlib.sha256()
    for name in ('benchmarks.py','fast.py','world.py'):
        digest.update((Path(__file__).parent/name).read_bytes())
    return digest.hexdigest()[:20]


def job_path(root,job):
    return Path(root)/job['family']/job['arm']/f'world_{job["world_seed"]:03d}'/f'seed_{job["seed"]:03d}'


def run_job(job,root,resume=True,overwrite=False):
    directory=job_path(root,job); identity=hashlib.sha256(json.dumps(dict(job=job,code=code_hash()),sort_keys=True).encode()).hexdigest()
    manifest_path=directory/'manifest.json'
    if manifest_path.exists():
        previous=json.loads(manifest_path.read_text())
        if resume and previous.get('identity')==identity and (directory/'complete.json').exists():
            return dict(status='reused',path=str(directory),seconds=0.)
        if not overwrite and not (resume and previous.get('identity')==identity):
            raise ValueError(f'Existing run differs: {directory}. Use a new output directory or --overwrite.')
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'complete.json').exists(): (directory/'complete.json').unlink()
    config=Config(**job['config']); options=job['world'].copy(); options['seed']=job['world_seed']; world=make_world(**options)
    start=time.perf_counter()
    atomic_json(manifest_path,dict(identity=identity,version=VERSION,code_hash=code_hash(),job=job,world=world.to_dict(),
        python=sys.version,numpy=np.__version__,scipy=__import__('scipy').__version__,status='running'))
    result=simulate(world,config,job['seed'],cache_provider(Path(root)/'_benchmarks',config.multistarts))
    with (directory/'periods.jsonl').open('w') as f:
        for row in result['periods']: f.write(json.dumps(clean(row),allow_nan=False)+'\n')
    atomic_json(directory/'summary.json',result['summary']); atomic_json(directory/'benchmarks.json',result['world_versions'])
    if result['idealized_oracle_price_variant']: atomic_json(directory/'idealized_oracle_price_variant.json',result['idealized_oracle_price_variant'])
    if result['executions']:
        with (directory/'executions.jsonl').open('w') as f:
            for row in result['executions']: f.write(json.dumps(row,allow_nan=False)+'\n')
    # Compact scalar CSV always available. Complete nested data remain in JSONL.
    scalar_keys=[k for k,v in result['periods'][0].items() if isinstance(v,(int,float,str,bool)) or v is None]
    with (directory/'periods.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=scalar_keys);writer.writeheader()
        for row in result['periods']: writer.writerow({k:row[k] for k in scalar_keys})
    formats=['jsonl','csv']
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        # Scalars plus serialized nested diagnostics: stable across zero-turn arms.
        parquet_rows=[{k:json.dumps(v,allow_nan=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in result['periods']]
        pq.write_table(pa.Table.from_pylist(parquet_rows),directory/'periods.parquet')
        pq.write_table(pa.Table.from_pylist([{k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in result['summary'].items()}]),directory/'summary.parquet')
        formats.append('parquet')
    except ImportError: pass
    seconds=time.perf_counter()-start
    atomic_json(directory/'complete.json',dict(identity=identity,seconds=seconds,formats=formats))
    return dict(status='completed',path=str(directory),seconds=seconds,summary=result['summary'])
