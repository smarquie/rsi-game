"""Reproduce the delivered exploratory study across every E1-E8 arm.

Usage: .venv/bin/python research.py --seeds 3 --cycles 100 --workers 4
Full paper scale: --seeds 50 --cycles 200 (substantially more computation).
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace, asdict
from pathlib import Path
import time
from rsi_game.experiments import arms
from rsi_game.run import save_run, dump
from rsi_game.equilibrium import solve, exhaustive
from rsi_game.episode import evaluate


def job(task):
    experiment,name,seed,sections,output=task
    dest=Path(output)/experiment/name/f'seed_{seed}'
    if experiment=='E5':
        cfg,tech=sections['agent'],sections['tech']; sol=solve(cfg,tech); ev=evaluate(sol.profile,cfg,tech)
        result=dict(solution=asdict(sol),Q=float(ev.Q[0]),W=float(ev.welfare[0]),exhaustive=exhaustive(cfg,tech,attractors=True))
        dump(dest/'object_analysis.json',result)
        dump(dest/'manifest.json',dict(parameters={k:asdict(v) for k,v in sections.items()}))
    else: save_run(dest,seed,sections)
    return f'{experiment}/{name}/{seed}'


def main():
    p=argparse.ArgumentParser(); p.add_argument('--seeds',type=int,default=3); p.add_argument('--cycles',type=int,default=100)
    p.add_argument('--workers',type=int,default=4); p.add_argument('--output',default='results/study')
    args=p.parse_args(); tasks=[]
    for i in range(1,9):
        experiment=f'E{i}'
        for name,sections in arms(experiment):
            sections['designer']=replace(sections['designer'],n_cycles=args.cycles)
            for seed in range(1 if i==5 else args.seeds): tasks.append((experiment,name,seed,sections,args.output))
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(job,t) for t in tasks]
        for i,f in enumerate(as_completed(futures),1): print(f'{i}/{len(tasks)} {f.result()}',flush=True)
    dump(Path(args.output)/'study_manifest.json',dict(seeds=args.seeds,cycles=args.cycles,runs=len(tasks),seconds=time.perf_counter()-start,
         scope='Exploratory all-arm E1-E8 study; not exhaustive continuous meta dynamics; empirical intervals across seeds'))

if __name__=='__main__': main()
