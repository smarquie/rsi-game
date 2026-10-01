"""CLI. Run `python -m rsi_game --help` from the project root."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import time
from .params import *
from .meta import run
from .equilibrium import solve, exhaustive, diagnostics, team_search
from .episode import evaluate
from .experiments import arms


def dump(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    # JSON uses null for an infinite decorrelation length in manifests.
    def clean(x):
        if isinstance(x, __import__('numpy').generic): x=x.item()
        if isinstance(x,float) and not __import__('math').isfinite(x): return 'Infinity' if x>0 else None
        if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
        if isinstance(x,(tuple,list)): return [clean(v) for v in x]
        return x
    path.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n')


def save_run(out,seed,sections):
    started=time.perf_counter(); rows=run(seed=seed,**sections)
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    with (out/'cycles.jsonl').open('w') as f:
        for row in rows: f.write(json.dumps(row,allow_nan=False)+'\n')
    dump(out/'manifest.json',dict(seed=seed,parameters={k:asdict(v) for k,v in sections.items()},seconds=time.perf_counter()-started,
        model_version='0.1.0',numpy_version=__import__('numpy').__version__,python_version=__import__('sys').version))
    return rows


def main():
    p=argparse.ArgumentParser(description='RSI Game research simulator')
    sub=p.add_subparsers(dest='command',required=True)
    default=dict(tech=TechParams(),agent=AgentConfig(),protocol=EvalProtocol(),meta=MetaParams(),designer=DesignerChoice())
    for cmd in ('simulate','analyze','suite'):
        sp=sub.add_parser(cmd); sp.add_argument('--output',default=f'results/{cmd}'); sp.add_argument('--config')
        if cmd=='simulate':
            sp.add_argument('--seed',type=int,default=0); sp.add_argument('--cycles',type=int); sp.add_argument('--K',type=str)
            sp.add_argument('--edit-class',type=int,choices=(1,2,3,4)); sp.add_argument('--exact',action='store_true')
        if cmd=='analyze': sp.add_argument('--exhaustive',action='store_true'); sp.add_argument('--attractors',action='store_true')
        if cmd=='suite':
            sp.add_argument('--experiment',choices=[f'E{i}' for i in range(1,9)],required=True)
            sp.add_argument('--seeds',type=int,default=50); sp.add_argument('--cycles',type=int,default=200)
            sp.add_argument('--max-arms',type=int); sp.add_argument('--exhaustive',action='store_true')
    sp=sub.add_parser('report'); sp.add_argument('--input',default='results'); sp.add_argument('--output',default='results/report.html')
    sp=sub.add_parser('defaults'); sp.add_argument('--output',default='config.json')
    args=p.parse_args()
    if args.command=='defaults': save(args.output,**default); return
    if args.command=='report':
        from .analysis import report
        report(args.input,args.output); print(args.output); return
    sections=load(args.config) if args.config else default
    if args.command=='simulate':
        edits={}
        if args.cycles is not None: edits['n_cycles']=args.cycles
        if args.K is not None: edits['K']=None if args.K.lower() in ('inf','infinity') else int(args.K)
        if args.edit_class is not None: edits['edit_class']=args.edit_class
        if args.exact: edits['exact']=True
        sections['designer']=replace(sections['designer'],**edits)
        rows=save_run(args.output,args.seed,sections)
        print(json.dumps({k:rows[-1][k] for k in ('Q','W','score','converged')} if rows else {},indent=2))
    elif args.command=='analyze':
        cfg,tech=sections['agent'],sections['tech']; sol=solve(cfg,tech); ev=evaluate(sol.profile,cfg,tech)
        result=dict(solution=asdict(sol),Q=float(ev.Q[0]),W=float(ev.welfare[0]),tokens=float(ev.T[0]),diagnostics=diagnostics(cfg,tech,sol.profile),team_search=team_search(cfg,tech,sol.profile))
        if args.exhaustive or args.attractors: result['exhaustive']=exhaustive(cfg,tech,attractors=args.attractors)
        dump(Path(args.output)/'object_analysis.json',result); print(json.dumps(result,indent=2))
    else:
        if args.config: p.error('--config is not supported for suite; experiment arms specify their own parameters')
        if args.seeds<1 or args.cycles<1: p.error('Positive seeds and cycles required')
        for index,(name,section) in enumerate(arms(args.experiment)):
            if args.max_arms is not None and index>=args.max_arms: break
            section['designer']=replace(section['designer'],n_cycles=args.cycles)
            for seed in range(1 if args.experiment=='E5' else args.seeds):
                folder=Path(args.output)/args.experiment/name/f'seed_{seed}'
                if args.experiment=='E5':
                    cfg,tech=section['agent'],section['tech']; sol=solve(cfg,tech); ev=evaluate(sol.profile,cfg,tech)
                    result=dict(solution=asdict(sol),Q=float(ev.Q[0]),W=float(ev.welfare[0]),diagnostics=diagnostics(cfg,tech,sol.profile),team_search=team_search(cfg,tech,sol.profile))
                    if args.exhaustive: result['exhaustive']=exhaustive(cfg,tech)
                    dump(folder/'object_analysis.json',result)
                else: save_run(folder,seed,section)
                print(f'{args.experiment} {name} seed={seed}',flush=True)

if __name__=='__main__': main()
