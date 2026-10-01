"""Version 0.4 CLI: inspect a plan before launching a potentially large study."""
import argparse
from dataclasses import asdict,replace
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import time
from .config import Config,load_config
from .world import make_world
from .experiments import plan,PRESETS
from .storage import atomic_json,run_job
from .benchmarks import benchmark_bundle,certify_global,idealized


def main(argv=None):
    parser=argparse.ArgumentParser(description='RSI functions game v0.4 — continuous decentralized learning')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('plan','suite'):
        p=sub.add_parser(name);p.add_argument('--preset',choices=PRESETS,default='pilot');p.add_argument('--families',nargs='+')
        p.add_argument('--worlds',type=int);p.add_argument('--replicates',type=int);p.add_argument('--periods',type=int);p.add_argument('--multistarts',type=int)
        p.add_argument('--keep-duplicates',action='store_true');p.add_argument('--output',default=f'results/v04/{name}')
        if name=='suite':
            p.add_argument('--workers',type=int,default=2);p.add_argument('--overwrite',action='store_true');p.add_argument('--max-jobs',type=int);p.add_argument('--no-report',action='store_true');p.add_argument('--contrasts')
    p=sub.add_parser('simulate');p.add_argument('--config');p.add_argument('--scenario',default='frustrated',choices=('concave','frustrated','interference','complements','example1','example2'))
    p.add_argument('--world-seed',type=int,default=0);p.add_argument('--seed',type=int,default=0);p.add_argument('--periods',type=int);p.add_argument('--multistarts',type=int)
    p.add_argument('--output',default='results/v04/single');p.add_argument('--overwrite',action='store_true');p.add_argument('--log-executions',action='store_true')
    p=sub.add_parser('benchmark');p.add_argument('--scenario',default='example2');p.add_argument('--world-seed',type=int,default=0);p.add_argument('--multistarts',type=int,default=300)
    p.add_argument('--certify',action='store_true');p.add_argument('--max-boxes',type=int,default=5000);p.add_argument('--tolerance',type=float,default=1e-5);p.add_argument('--output',default='results/v04/benchmark.json')
    p=sub.add_parser('report');p.add_argument('--input',default='results/v04/pilot');p.add_argument('--output');p.add_argument('--contrasts')
    p=sub.add_parser('calibrate');p.add_argument('--worlds',type=int,default=50);p.add_argument('--multistarts',type=int,default=300);p.add_argument('--output',default='results/v04/calibration.json')
    p=sub.add_parser('basins');p.add_argument('--resolution',type=int,default=21);p.add_argument('--periods',type=int,default=150)
    p.add_argument('--mode',choices=('fixed_low','fixed_high','learning'),default='fixed_low');p.add_argument('--output',default='results/v04/basins.json')
    p=sub.add_parser('defaults');p.add_argument('--output',default='configs/v04/default.json')
    args=parser.parse_args(argv)
    if args.command=='defaults':
        atomic_json(args.output,dict(world=dict(scenario='frustrated',n=5),config=asdict(Config())));return
    if args.command=='report':
        from .analysis import report
        report(args.input,args.output,contrasts=args.contrasts);return
    if args.command=='benchmark':
        world=make_world(args.scenario,seed=args.world_seed); result=benchmark_bundle(world,args.multistarts)
        if args.certify: result['certificate']=certify_global(world,result['team']['best']['q'],args.tolerance,args.max_boxes)
        atomic_json(args.output,dict(world=world.to_dict(),benchmarks=result));print(json.dumps(result['team']['best'],indent=2));return
    if args.command=='calibrate':
        from .diagnostics import calibration
        atomic_json(args.output,calibration(args.worlds,args.multistarts));return
    if args.command=='basins':
        from .diagnostics import basin_map
        data=basin_map(args.resolution,args.periods,args.mode);atomic_json(args.output,data)
        try:
            from .plots import plot_basin
            plot_basin(data,args.output)
        except ImportError: pass
        return
    if args.command=='simulate':
        world,config=load_config(args.config) if args.config else (dict(scenario=args.scenario),Config())
        changes={k:getattr(args,k) for k in ('periods','multistarts') if getattr(args,k) is not None}
        if args.log_executions: changes['log_executions']=True
        config=replace(config,**changes)
        job=dict(family='single',arm=world.get('scenario','custom'),world_seed=args.world_seed,seed=args.seed,world=world,config=asdict(config))
        result=run_job(job,args.output,overwrite=args.overwrite);print(json.dumps(result,indent=2));return
    design=plan(args.preset,args.families,args.worlds,args.replicates,args.periods,args.multistarts,args.keep_duplicates)
    out=Path(args.output)
    if args.command=='plan':
        path=out if out.suffix=='.json' else out/'plan.json';atomic_json(path,design)
        print(json.dumps({k:v for k,v in design.items() if k not in ('arms','jobs')},indent=2));print(f'Plan: {path}');return
    if args.workers<1: parser.error('--workers must be positive')
    if args.max_jobs is not None and args.max_jobs<1: parser.error('--max-jobs must be positive')
    out.mkdir(parents=True,exist_ok=True);atomic_json(out/'plan.json',design)
    jobs=design['jobs'][:args.max_jobs] if args.max_jobs else design['jobs'];failed=[];results=[];start=time.perf_counter()
    print(f'Running {len(jobs)} / {design["job_count"]} prepared jobs with {args.workers} workers',flush=True)
    pool=ProcessPoolExecutor(max_workers=args.workers)
    try:
        futures={pool.submit(run_job,job,str(out),True,args.overwrite):job for job in jobs}
        for index,future in enumerate(as_completed(futures),1):
            job=futures[future]
            try:
                result=future.result();results.append(result)
                print(f'{index}/{len(jobs)} {result["status"]}: {job["family"]}/{job["arm"]}/world{job["world_seed"]}/seed{job["seed"]}',flush=True)
            except Exception as error:
                failed.append(dict(job=job,error=f'{type(error).__name__}: {error}'));print(f'FAILED {job["family"]}/{job["arm"]}: {error}',flush=True)
    except KeyboardInterrupt:
        for future in futures: future.cancel()
        print('Interrupted: pending jobs cancelled. Active jobs may finish; completed jobs are durable. Rerun the same command to resume.',flush=True)
        pool.shutdown(wait=True,cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    atomic_json(out/'suite_summary.json',dict(requested=len(jobs),completed=len(results),failures=failed,seconds=time.perf_counter()-start,partial=len(jobs)<design['job_count']))
    print(f'Completed {len(results)}; failed {len(failed)}. Report: python -m rsi_game.v04 report --input {out}')
    if not args.no_report:
        from .analysis import report
        report(out,contrasts=args.contrasts)
    if failed: raise SystemExit(1)

if __name__=='__main__':main()
