"""Auditable all-run report; worlds, not executions, are statistical units."""
from pathlib import Path
from collections import defaultdict,Counter
import csv,html,json
import numpy as np
from .storage import atomic,digest

def csvfile(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with open(path,'w') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)

def interval(values,seed=505):
    a=np.array(values,dtype=float)
    if not len(a):return (None,None,None)
    if len(a)<2:return (float(a.mean()),None,None)
    rng=np.random.default_rng(seed);means=np.mean(rng.choice(a,(2000,len(a)),replace=True),axis=1)
    return float(a.mean()),float(np.quantile(means,.025)),float(np.quantile(means,.975))

def table(rows):
    if not rows:return '<p>No observations.</p>'
    keys=list(dict.fromkeys(k for r in rows for k in r));esc=lambda v:html.escape(str(v))
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(r.get(k,''))+'</td>' for k in keys)+'</tr>' for r in rows)+'</tbody></table></div>'

def document(title,body):return '<!doctype html><html><head><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{font:16px system-ui;max-width:1250px;margin:40px auto;padding:20px;color:#193044}h1,h2{color:#143957}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left;font-size:13px}.scroll{overflow:auto}a{color:#006b9a}img{max-width:100%}pre{white-space:pre-wrap}</style></head><body><h1>'+html.escape(title)+'</h1>'+body+'</body></html>'

def report(root):
    root=Path(root);out=root/'research';out.mkdir(parents=True,exist_ok=True);(out/'runs').mkdir(exist_ok=True)
    plan=json.loads((root/'plan.json').read_text());records=[];invalid=[];hashes=set();effects=[];details=[];horizons=[];periodfile=(out/'all_periods.csv').open('w');periodwriter=None;groups=defaultdict(list);matched=defaultdict(dict)
    for job in plan['jobs']:
        p=root/'runs'/job['id'];marker=p/'complete.json'
        if not marker.exists():invalid.append(dict(id=job['id'],status='missing'));continue
        completion=json.loads(marker.read_text());manifest=json.loads((p/'manifest.json').read_text())
        if manifest['job']!=job or any(not (p/name).exists() or digest(p/name)!=checksum for name,checksum in completion['checksums'].items()):invalid.append(dict(id=job['id'],status='integrity_failure'));continue
        hashes.add(manifest['code_hash']);data=json.loads((p/'result.json').read_text());common=dict(id=job['id'],family=job['family'],arm=job['arm'],world_seed=job['world_seed'],archetype=job['world']['archetype'],process='independent' if job.get('kind')=='independent' else job['config']['remedy'])
        if data.get('kind')=='paired':
            effect=dict(**common,**data['effects']);effect['ceiling_fraction']=abs(effect['F'])/effect['headroom'] if effect['headroom']>1e-9 else None;effect['ceiling_bin']=int(np.searchsorted([.01,.05,.1,.25,.5,1.],effect['ceiling_fraction'])) if effect['ceiling_fraction'] is not None else None;effects.append(effect);subsets=data['arms'];body='<h2>Paired effects</h2>'+table([data['effects']])
        elif data.get('kind')=='structural':
            details.append(dict(**common,accepted=','.join(data['accepted']),evaluations=data['evaluations'],resources=data['resources']));subsets={};body=table(details[-1:])+table([{k:v for k,v in e.items() if k!='trial'} for e in data['episodes']])
        else:subsets={'run':data};body=''
        for sub,result in subsets.items():
            row=dict(**common,subarm=sub,world_identity=__import__('hashlib').sha256(json.dumps(result['world'],sort_keys=True).encode()).hexdigest(),**result['summary'],**{f'descriptor_{k}':v for k,v in result['descriptors'].items()});records.append(row);groups[(job['family'],job['arm'],sub)].append(row)
            body+='<h2>'+html.escape(sub)+'</h2>'+table([result['summary']])+'<h3>All period diagnostics</h3>'+table([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in result['periods']])
            body+='<h3>Accessibility evidence</h3><pre>'+html.escape(json.dumps(result['accessibility'],indent=2))+'</pre>'
            for period in result['periods']:
                flat=dict(**common,subarm=sub,**{k:v for k,v in period.items() if k in ('period','deployment_Y','deployment_spending','improvement','opportunity','fraction','evaluations','resources','mean_Y','mean_spending','overload','price')})
                if periodwriter is None:periodwriter=csv.DictWriter(periodfile,fieldnames=list(flat));periodwriter.writeheader()
                periodwriter.writerow(flat)
            for h in (300,1000,3000):
                if h<=result['summary']['periods']:
                    pr=result['periods'][h];horizons.append(dict(**common,subarm=sub,horizon=h,**{k:pr[k] for k in ('deployment_Y','improvement','opportunity','fraction','evaluations','resources')}))
            if sub=='run':
                w=job['world'].copy();w.pop('seed',None);config=job['config'].copy();process=config.pop('remedy',None)
                if process=='random_schedule':config['schedule']='rotation'
                if process=='adaptive_commit':config['commit']='fixed'
                if process=='damping03':config['beta']=.7
                key=(job['family'],json.dumps(w,sort_keys=True),json.dumps(config,sort_keys=True),job['world_seed']);matched[key].setdefault('independent' if job.get('kind')=='independent' else job['config']['remedy'],[]).append(row)
        body+='<h2>Inputs and provenance</h2><pre>'+html.escape(json.dumps(manifest,indent=2))+'</pre><p><a href="../../runs/'+job['id']+'/result.json">Complete machine-readable result, including fitted coefficients and benchmark candidates</a></p>'
        (out/'runs'/f'{job["id"]}.html').write_text(document(job['family']+' / '+job['arm'],body))
    matched={key:{process:average_replicas(items) for process,items in methods.items()} for key,methods in matched.items()}
    if len(hashes)>1:raise ValueError('Mixed code hashes: report refused. Use separate output roots.')
    stats=[]
    metrics=('final_Y','improvement','opportunity','fraction','tail_std','total_overload','evaluations','resources','misallocation','tau_absolute_evaluations','tau_fraction_evaluations','tau_absolute_resources')
    for (family,arm,sub),items in groups.items():
        for metric in metrics:
            byworld=defaultdict(list)
            for r in items:
                if r.get(metric) is not None:byworld[r['world_seed']].append(r[metric])
            values=[np.mean(v) for v in byworld.values()];mean,lo,hi=interval(values)
            stats.append(dict(family=family,arm=arm,subarm=sub,metric=metric,worlds=len(values),mean=mean,ci_low=lo,ci_high=hi))
        for metric in ('tau_absolute','tau_fraction'):
            times=[r[metric] for r in items if r[metric] is not None];n=len(items)
            # RMST at common observed horizon includes right-censored runs.
            horizon=min(r['periods'] for r in items);restricted=[min(r[metric],horizon) if r[metric] is not None else horizon for r in items]
            restricted_worlds=defaultdict(list)
            for item,value in zip(items,restricted):restricted_worlds[item['world_seed']].append(value)
            mean,lo,hi=interval([np.mean(v) for v in restricted_worlds.values()])
            stats.append(dict(family=family,arm=arm,subarm=sub,metric=metric+'_restricted_mean',worlds=len(restricted_worlds),runs=n,mean=mean,ci_low=lo,ci_high=hi,events=len(times),censored=n-len(times),horizon=horizon))
    from .inference import paired_sign_test,holm
    contrasts=[]
    for family in sorted({key[0] for key in matched}):
        for remedy in sorted({k for key,v in matched.items() if key[0]==family for k in v}-{'baseline'}):
            for metric in ('improvement','fraction','tail_std'):
                clustered=defaultdict(list)
                for (fam,_,_,seed),v in matched.items():
                    if fam==family and remedy in v and 'baseline' in v and v[remedy].get(metric) is not None and v['baseline'].get(metric) is not None:clustered[seed].append(v[remedy][metric]-v['baseline'][metric])
                vals=[np.mean(v) for v in clustered.values()];mean,lo,hi=interval(vals)
                contrasts.append(dict(family=family,remedy=remedy,metric=metric,paired_cells=sum(map(len,clustered.values())),world_clusters=len(clustered),mean_difference=mean,ci_low=lo,ci_high=hi,p_value=paired_sign_test(vals),inference='Paired sign randomization; symmetric-difference null; Holm within experiment family. Marginal 95% world-bootstrap CI.'))
    holm(contrasts)
    effort_pairs=[];effort_groups=defaultdict(lambda:defaultdict(list))
    for (family,_,_,seed),runs in matched.items():
        if 'baseline' not in runs:continue
        baselines=[json.loads((root/'runs'/identity/'result.json').read_text())['periods'] for identity in runs['baseline']['_replica_ids']]
        for remedy,row in runs.items():
            if remedy=='baseline':continue
            trajectories=[json.loads((root/'runs'/identity/'result.json').read_text())['periods'] for identity in row['_replica_ids']]
            for budget_type in ('evaluations','resources'):
                budget=min(trace[-1][budget_type] for trace in baselines+trajectories)
                left=[next(r for r in reversed(trace) if r[budget_type]<=budget) for trace in baselines]
                right=[next(r for r in reversed(trace) if r[budget_type]<=budget) for trace in trajectories]
                difference=float(np.mean([r['improvement'] for r in right])-np.mean([r['improvement'] for r in left]))
                effort_pairs.append(dict(family=family,remedy=remedy,world_seed=seed,budget_type=budget_type,budget=budget,baseline_consumed=float(np.mean([r[budget_type] for r in left])),treatment_consumed=float(np.mean([r[budget_type] for r in right])),baseline_replicas=len(left),treatment_replicas=len(right),improvement_difference=difference))
                effort_groups[(family,remedy,budget_type)][seed].append(difference)
    effort_statistics=[]
    for (family,remedy,budget_type),byseed in effort_groups.items():
        vals=[np.mean(v) for v in byseed.values()];mean,lo,hi=interval(vals)
        effort_statistics.append(dict(family=family,remedy=remedy,budget_type=budget_type,world_clusters=len(vals),mean_difference=mean,ci_low=lo,ci_high=hi,p_value=paired_sign_test(vals)))
    holm(effort_statistics);csvfile(out/'matched_effort_pairs.csv',effort_pairs);csvfile(out/'matched_effort_statistics.csv',effort_statistics)
    effectstats=[]
    for arm in sorted({r['arm'] for r in effects}):
        for metric in ('D','F','Gamma0','Gamma1','A'):
            vals=[r[metric] for r in effects if r['arm']==arm];mean,lo,hi=interval(vals);effectstats.append(dict(arm=arm,metric=metric,worlds=len(vals),mean=mean,ci_low=lo,ci_high=hi))
    csvfile(out/'all_runs.csv',records);periodfile.close();csvfile(out/'horizon_outcomes.csv',horizons);csvfile(out/'all_arm_statistics.csv',stats);csvfile(out/'paired_contrasts.csv',contrasts);csvfile(out/'intervention_effects.csv',effects);csvfile(out/'intervention_statistics.csv',effectstats);csvfile(out/'structural_selection.csv',details);csvfile(out/'coverage.csv',invalid)
    figures=''
    if records:
        import os
        os.environ.setdefault('MPLCONFIGDIR',str(out/'_matplotlib'))
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(1,2,figsize=(12,4));counts=Counter(r['failure_class'] for r in records);axs[0].bar(range(len(counts)),list(counts.values()));axs[0].set_xticks(range(len(counts)),[k.split('_')[0] for k in counts]);axs[0].set_title('Observed outcome classes (all runs)');axs[0].set_ylabel('Run count')
        pts=[r for r in records if r['fraction'] is not None];axs[1].scatter([r['descriptor_coupling_ratio'] for r in pts],[r['fraction'] for r in pts],s=12,alpha=.5);axs[1].set_xlabel('Coupling ratio');axs[1].set_ylabel('Captured best-found headroom');fig.tight_layout();fig.savefig(out/'outcomes.png',dpi=160);plt.close(fig);figures='<img src="outcomes.png" alt="Outcome classes and coupling versus captured headroom">'
    valid=len(plan['jobs'])-len(invalid);status='COMPLETE' if not invalid else 'PARTIAL — missing or invalid jobs'
    intro=f'<p><strong>{status}</strong>: {valid}/{len(plan["jobs"])} jobs verified. Code hashes: {html.escape(str(sorted(hashes)))}</p>'
    interpretation='<p>Feasible deployment is the outcome. Uncertified ceilings give lower bounds on opportunity and upper bounds on captured headroom. A missing speed event is right-censored, never zero. F/G classifications are candidates, not proofs. R7 includes oracle budget feasibility. Periods and executions are repeated observations, not independent samples. Smoke/pilot runs validate machinery and do not establish research conclusions.</p><p>Intervals are world-bootstrap estimates; one-world cells have no confidence interval. Paired comparison p-values use sign randomization and Holm correction within each experiment family; the displayed confidence intervals are marginal, not simultaneous. These tests assume exchangeable signs under the paired null. Prespecify comparisons before examining held-out data.</p>'
    links='<ul>'+''.join('<li><a href="runs/'+j['id']+'.html">'+html.escape(j['family']+' / '+j['arm']+' / world '+str(j['world_seed']))+'</a></li>' for j in plan['jobs'] if (out/'runs'/f'{j["id"]}.html').exists())+'</ul>'
    body=intro+interpretation+figures+'<h2>All arm statistics</h2>'+table(stats)+'<h2>Matched baseline comparisons</h2>'+table(contrasts)+'<h2>Comparisons at a common effort budget</h2><p>Last completed period at or below the common budget. Actual consumed resources are retained in the paired CSV; discretization can leave unequal unused remainders.</p>'+table(effort_statistics)+'<h2>Structural intervention effects</h2>'+table(effectstats)+'<h2>Coverage problems</h2>'+table(invalid)+'<h2>Every run</h2>'+links
    (out/'research_report.html').write_text(document('RSI v0.5 research report',body))
    atomic(out/'report_manifest.json',dict(status=status,planned=len(plan['jobs']),verified=valid,code_hashes=sorted(hashes),plan_sha256=digest(root/'plan.json'),files={p.name:digest(p) for p in out.glob('*.csv')}))
    return out/'research_report.html'


def average_replicas(items):
    """A world remains one observation even when its schedule is replicated."""
    result=items[0].copy()
    for key in result:
        values=[r[key] for r in items if isinstance(r.get(key),(int,float))]
        if values:result[key]=float(np.mean(values))
    result['_replica_ids']=[r['id'] for r in items]
    return result
