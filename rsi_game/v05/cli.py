"""Prepare, inspect, execute and report frozen v0.5 research plans."""
import argparse,json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from .experiments import plan,preflight
from .storage import atomic,run_job,digest
from .research_report import report

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--study',choices=('core','tuning','typology','examples','structural','broad','stability','continuation','structural-test','long','readiness'),default='core');p.add_argument('--preset',choices=('smoke','pilot','paper','full'),default='pilot');p.add_argument('--selection');p.add_argument('--output',required=True)
    p=sub.add_parser('suite');p.add_argument('--plan',required=True);p.add_argument('--output',required=True);p.add_argument('--workers',type=int,default=2);p.add_argument('--max-jobs',type=int);p.add_argument('--no-report',action='store_true')
    p=sub.add_parser('report');p.add_argument('--input',required=True)
    p=sub.add_parser('select');p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('select-structural');p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('typology-analysis');p.add_argument('--input',required=True)
    p=sub.add_parser('estimate');p.add_argument('--plan',required=True);p.add_argument('--pilot',required=True);p.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.command=='estimate':
        import numpy as np
        p=json.loads(Path(args.plan).read_text());pilot=Path(args.pilot);rates=[];sizes=[]
        for marker in (pilot/'runs').glob('*/complete.json'):
            m=json.loads(marker.read_text());j=json.loads((marker.parent/'manifest.json').read_text())['job'];periods=j['config']['periods']*(4 if j.get('kind')=='paired' else 1)
            if j.get('kind')=='structural':continue
            rates.append(m['seconds']/max(1,periods));sizes.append(sum(f.stat().st_size for f in marker.parent.iterdir() if f.is_file())/max(1,periods))
        if not rates:raise ValueError('Need completed pilot runs')
        periods=sum(j['config']['periods']*(4 if j.get('kind')=='paired' else 1) for j in p['jobs'])
        print(json.dumps(dict(jobs=len(p['jobs']),learning_periods=periods,observed_seconds_per_period_quantiles=np.quantile(rates,[.1,.5,.9]).tolist(),rough_wall_days_quantiles=(np.quantile(rates,[.1,.5,.9])*periods/max(1,args.workers)/86400).tolist(),rough_raw_disk_GB=float(np.median(sizes)*periods/1e9),limitations='Extrapolation, not a bound. Dimension, optimizer difficulty, diagnostics, benchmark reuse and reporting change costs. Benchmark representative dimensions first.'),indent=2));return
    if args.command=='typology-analysis':
        from .typology_analysis import analyze
        print(analyze(args.input));return
    if args.command=='plan':
        selection=json.loads(Path(args.selection).read_text()) if args.selection else None
        result=plan(args.study,args.preset,selection);atomic(args.output,result)
        counts=sum(j['config']['periods']*(4 if j.get('kind')=='paired' else 1) for j in result['jobs'])
        print(f'Prepared {len(result["jobs"]):,} jobs, approximately {counts:,} learning periods. Plan: {Path(args.output).resolve()}');return
    if args.command=='report':print(report(args.input));return
    if args.command=='select-structural':
        from collections import Counter
        root=Path(args.input);p=json.loads((root/'plan.json').read_text())
        if p['study']!='structural':raise ValueError('Expected structural selection study')
        counts=Counter();costs=dict(evaluations=0,resources=0.);sources=[]
        for j in p['jobs']:
            path=root/'runs'/j['id']
            if j['world_seed']>=100 or not (path/'complete.json').exists():raise ValueError('Finish selection on seeds 0-99 first')
            marker=json.loads((path/'complete.json').read_text())
            if any(digest(path/k)!=v for k,v in marker['checksums'].items()):raise ValueError('Structural input integrity failed')
            r=json.loads((path/'result.json').read_text());counts.update(set(r['transferable_process_edits']));costs['evaluations']+=r['evaluations'];costs['resources']+=r['resources'];sources.append(digest(path/'result.json'))
        selected=sorted((u for u,c in counts.items() if c/len(p['jobs'])>=.5),key=lambda u:(-counts[u],u))
        atomic(args.output,dict(process_edits=selected,criterion='Process edits accepted in at least half of selection runs; frequency order then catalogue order. Each prefix is tested.',counts=dict(counts),selection_costs=costs,sources=sources,preset=p['preset']))
        print('Transferable edit sequence:',selected);return
    if args.command=='select':
        root=Path(args.input);p=json.loads((root/'plan.json').read_text())
        if p['study']!='tuning':raise ValueError('Selection must use the tuning study only')
        from collections import defaultdict
        import numpy as np
        values=defaultdict(lambda:defaultdict(list));sources=[]
        for j in p['jobs']:
            if j['world_seed']>=100:raise ValueError('Held-out world in tuning data')
            path=root/'runs'/j['id'];marker=path/'complete.json'
            if not marker.exists():raise ValueError('Finish all tuning jobs before selection')
            completion=json.loads(marker.read_text())
            if any(digest(path/k)!=v for k,v in completion['checksums'].items()):raise ValueError('Tuning integrity failure')
            data=json.loads((path/'result.json').read_text());remedy=j['config']['remedy']
            if remedy not in ('baseline','oracle','R7'):
                key=json.dumps(j['world'],sort_keys=True)
                values[remedy][key].append(data['summary']['improvement'])
            sources.append(dict(id=j['id'],sha256=digest(path/'result.json')))
        scores={k:float(np.mean([np.mean(v) for v in worlds.values()])) for k,worlds in values.items()};ranking=sorted(scores,key=lambda k:(-scores[k],k));atomic(args.output,dict(selected=ranking[:3],criterion='Mean absolute deployment improvement, replicas averaged within world first; oracle and R7 excluded; ties alphabetic. Headroom fractions remain secondary reported outcomes.',scores=scores,source_plan_sha256=digest(root/'plan.json'),source_results=sources,seed_range=[0,99],preset=p['preset']))
        print('Selected:',', '.join(ranking[:3]));return
    if args.workers<1:raise ValueError('workers must be positive')
    p=json.loads(Path(args.plan).read_text());root=Path(args.output);saved=root/'plan.json'
    if saved.exists() and json.loads(saved.read_text())!=p:raise ValueError('Output contains a different plan; choose a new output directory')
    preflight(p['jobs'])
    atomic(saved,p);jobs=p['jobs'][:args.max_jobs] if args.max_jobs else p['jobs'];failures=[]
    print(f'Running {len(jobs)} / {len(p["jobs"])} prepared jobs with {args.workers} workers',flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        iterator=iter(jobs);pending={};finished=0
        def refill():
            while len(pending)<2*args.workers:
                try:j=next(iterator)
                except StopIteration:return
                pending[pool.submit(run_job,j,str(root))]=j['id']
        refill()
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for f in done:
                identity=pending.pop(f);finished+=1
                try:r=f.result();print(f'{finished}/{len(jobs)} {r["id"]} {r["status"]}',flush=True)
                except Exception as e:failures.append(dict(id=identity,error=str(e)));print(f'FAILED {identity}: {e}',flush=True)
            refill()
    atomic(root/'failures.json',failures)
    if not args.no_report:print(report(root))
    if failures:raise SystemExit(1)
