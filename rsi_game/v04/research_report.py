"""Complete, auditable research-report bundle. Reads results; never reruns the model."""
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import csv
import hashlib
import html
import json
import platform
import numpy as np
from .storage import atomic_json

REPORT_VERSION='1.0'
DEFINITIONS={
 'final_Y':'Raw mean aggregate in the final period; may include infeasible executions.',
 'final_reward':'Final aggregate minus the configured overload penalty.',
 'improvement':'Final raw aggregate minus period-zero raw aggregate; not a causal treatment effect.',
 'gap_to_best_found':'Feasible team best-found minus final raw aggregate. Negative values may reflect overload.',
 'total_overload':'Sum of per-period overload; horizon dependent. Fixed periods use average-budget overload; adaptive periods average positive execution overload.',
 'mean_overload':'Mean overload across all logged periods, including period zero.',
 'overload_period_fraction':'Fraction of logged periods with overload above 1e-8.',
 'tail_mean_Y':'Mean raw aggregate across the last min(20, number of observations) periods.',
 'tail_mean_reward':'Mean penalized reward over the same final window.',
 'tail_target_range':'Largest coordinate range over the last up to 20 periods. Finite-horizon motion diagnostic.',
 'tail_price_range':'Maximum minus minimum price over the final up to 20 periods.',
 'settling_period':'First period of a suffix of at least 20 observations within 1% of final Y. Null means not observed; conditional means exclude censored runs.',
 'settling_observed':'1 if the outcome settling criterion was observed, 0 otherwise; not a setting-convergence test.',
 'skipped_turns':'Number of scheduled function turns not executed.',
 'skip_fraction':'Skipped function turns / scheduled function turns; null if none scheduled.',
 'jump_events':'Number of logged fast-game jump events.',
 'bound_violations':'Number of execution-coordinate commitment-bound violations.',
 'target_path_length':'Sum of Euclidean target displacements between periods.',
 'mean_absolute_staleness':'Mean absolute local-slope belief error over functions and periods, including initial priors.',
 'max_valid_identification_error':'Maximum absolute fitted slope/curvature error only on updates satisfying logged exact-identification conditions; null if no eligible fits.',
 'eligible_fit_count':'Number of updates satisfying exact-identification conditions.',
 'fit_count':'Number of successful local regression updates.',
 'max_curvature_fit_error':'Largest absolute curvature-fit error over all updates, whether or not exact premises hold.',
 'max_slope_fit_error':'Largest absolute slope-fit error over all updates.',
 'max_exploration_formula_error':'Largest exploration-effect prediction error over periods with logged applicability.',
 'max_complementarity_residual':'Largest logged resource price/complementarity residual.',
 'final_target_budget_excess':'Positive part of final target spending minus the final world budget.',
 'final_budget_feasible':'1 if final logged mean spending is within budget +1e-8; average-feasibility diagnostic only.',
 'within_one_percent_best':'Raw final Y within 1% of best-found Y; interpret jointly with feasibility.',
 'global_certified':'1 if final team benchmark carries the solver global-certification flag.',
 'initial_Y':'Period-zero raw aggregate.',
}
PRIMARY=('final_Y','final_reward','tail_mean_reward','mean_overload','tail_target_range','settling_observed','skip_fraction','max_valid_identification_error')


def stats(values):
    x=np.asarray([v for v in values if v is not None and np.isfinite(v)],float)
    if not len(x):return dict(n=0,mean=None,median=None,sd=None,min=None,max=None,ci95_low=None,ci95_high=None)
    lo=hi=None
    if len(x)>1:
        rng=np.random.default_rng(4104); means=np.mean(x[rng.integers(0,len(x),(4000,len(x)))],axis=1)
        lo,hi=map(float,np.quantile(means,[.025,.975]))
    return dict(n=len(x),mean=float(x.mean()),median=float(np.median(x)),sd=float(x.std(ddof=1)) if len(x)>1 else None,
                min=float(x.min()),max=float(x.max()),ci95_low=lo,ci95_high=hi)


def csv_write(path,rows,fields=None):
    rows=list(rows);fields=fields or (list(rows[0]) if rows else ['status'])
    with Path(path).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)


def fmt(x):return 'not estimable' if x is None else f'{x:.6g}' if isinstance(x,(int,float)) else str(x)
def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(fmt(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def paragraph(text):return '<p>'+html.escape(text)+'</p>'
def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{font:15px/1.65 system-ui;max-width:1200px;margin:40px auto;padding:0 24px;color:#203047}h1,h2,h3{line-height:1.25}h2{margin-top:40px;border-bottom:1px solid #ccd6df;padding-bottom:10px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:8px;border-bottom:1px solid #dde3e9;text-align:left;vertical-align:top}th{background:#eff4f7}.scroll{overflow:auto}pre{white-space:pre-wrap;font-size:12px;background:#f4f6f8;padding:15px}a{color:#087d78}.note{background:#fff5df;padding:18px}@media print{body{max-width:none;margin:0;font-size:10pt}h2{break-before:page}tr{break-inside:avoid}.scroll{overflow:visible}a{color:inherit}}</style><h1>'+html.escape(title)+'</h1>'+body+'</html>'


def extended_metrics(summary,rows,versions,base):
    d=base(summary,rows);tail=rows[-20:];fits=[u for r in rows for u in r['updates'].values() if u.get('updated')]
    planned=sum(len(r['planned_explorers']) for r in rows);budget=versions[-1]['world']['B']
    d.update(mean_overload=float(np.mean([r['overload'] for r in rows])),overload_period_fraction=float(np.mean([r['overload']>1e-8 for r in rows])),
      tail_mean_Y=float(np.mean([r['mean_Y'] for r in tail])),tail_mean_reward=float(np.mean([r['reward'] for r in tail])),tail_price_range=float(np.ptp([r['price'] for r in tail])),
      settling_observed=float(summary['settling_period'] is not None),skip_fraction=summary['skipped_turns']/planned if planned else None,
      eligible_fit_count=sum(u['exact_identification_conditions'] for u in fits),fit_count=len(fits),
      max_complementarity_residual=max(r['complementarity_residual'] for r in rows),
      final_target_budget_excess=max(0.,summary['final_target_spending']-budget),final_budget_feasible=float(rows[-1]['mean_spending']<=budget+1e-8),global_certified=float(summary['global_certified']))
    return d


def build(root,destination,base_metrics,contrast_path=None):
    root=Path(root);out=Path(destination);out.mkdir(parents=True,exist_ok=True);(out/'runs').mkdir(exist_ok=True)
    plan=json.loads((root/'plan.json').read_text()) if (root/'plan.json').exists() else {}
    suite=json.loads((root/'suite_summary.json').read_text()) if (root/'suite_summary.json').exists() else {}
    def jobkey(j):return (j['family'],j['arm'],j['world_seed'],j['seed'])
    expected_jobs={jobkey(j):j for j in plan.get('jobs',[])};expected=set(expected_jobs);found=set();records=[];issues=[];inputs=[];groups=defaultdict(lambda:defaultdict(list));versions_seen=set();hashes=set();arm_jobs={};events=[];benchmarks=[]
    from .analysis import TEMPLATE
    for marker in sorted(root.glob('**/complete.json')):
        folder=marker.parent
        try:
            manifest=json.loads((folder/'manifest.json').read_text());complete=json.loads(marker.read_text());job=manifest['job'];key=jobkey(job)
            if complete['identity']!=manifest['identity']:raise ValueError('Completion/manifest identity mismatch')
            if key in found:raise ValueError('Duplicate job identity in input tree')
            if key in expected_jobs and job!=expected_jobs[key]:raise ValueError('Run configuration differs from the declared study plan')
            if key[:2] in arm_jobs and any(job[k]!=arm_jobs[key[:2]][k] for k in ('world','config')):raise ValueError('Inconsistent configurations within one arm; use separate arm names')
            summary=json.loads((folder/'summary.json').read_text());rows=[json.loads(s) for s in (folder/'periods.jsonl').read_text().splitlines()];versions=json.loads((folder/'benchmarks.json').read_text())
            if [r['period'] for r in rows]!=list(range(job['config']['periods']+1)):raise ValueError('Period coverage is incomplete or unordered')
            values=extended_metrics(summary,rows,versions,base_metrics)
        except (KeyError,ValueError,OSError,TypeError) as error:
            issues.append(dict(path=str(folder.relative_to(root)),error=str(error)));continue
        found.add(key);hashes.add(manifest.get('code_hash'));versions_seen.add((manifest.get('python'),manifest.get('numpy'),manifest.get('scipy')))
        arm=key[:2];arm_jobs[arm]=job;groups[arm][key[2]].append(values)
        rid='run-'+hashlib.sha256('/'.join(map(str,key)).encode()).hexdigest()[:16]
        record=dict(run_id=rid,family=key[0],arm=key[1],world=key[2],seed=key[3],source=str(folder.relative_to(root)),**values);records.append(record)
        for name in ('manifest.json','complete.json','summary.json','periods.jsonl','benchmarks.json'):
            p=folder/name;inputs.append(dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        for v in versions:
            b=v['benchmarks']['team'];best=b['best']
            benchmarks.append(dict(run_id=rid,world_version_period=v['period'],Y=best['Y'],spending=best['spending'],global_certified=b['global_certified'],candidate_count=len(b['validated_stationary_points']),details=json.dumps(b)))
        for r in rows:
            if r['outside_event']:
                before=[v for v in rows if max(0,r['period']-20)<=v['period']<r['period']];after=[v for v in rows if r['period']<=v['period']<r['period']+20]
                events.append(dict(run_id=rid,period=r['period'],kind=r['outside_event']['kind'],pre_n=len(before),post_n=len(after),pre_Y=float(np.mean([v['mean_Y'] for v in before])) if before else None,post_Y=float(np.mean([v['mean_Y'] for v in after])),event=json.dumps(r['outside_event'])))
        compact=[{k:r[k] for k in ('period','mean_Y','reward','price','overload','mean_spending','mean_settings','targets','staleness_error','exploration_effect','predicted_exploration_effect','best_found_Y','skipped','fast_status')} for r in rows]
        run=dict(name='/'.join(map(str,key)),summary=summary,job=job,benchmarks=versions,rows=compact)
        data=dict(runs=[run],aggregate=[],contrasts=[],count=1,planned=1,preset='individual appendix',notes=[],suite=dict(source=record['source'],identity=manifest['identity']))
        detail='<h2>Complete scalar period record</h2>'+table(['Period','Y','Reward','Price','Mean spending','Overload','Target spending','Fast status'],[[r[k] for k in ('period','mean_Y','reward','price','mean_spending','overload','target_spending','fast_status')] for r in rows])
        detail+='<h2>Every recorded metric</h2>'+table(['Metric','Value'],values.items())+'<h2>Benchmark audit: every world version</h2><pre>'+html.escape(json.dumps(versions,indent=2))+'</pre>'
        detail+='<h2>Reproduction manifest</h2><pre>'+html.escape(json.dumps(manifest,indent=2))+'</pre>'
        detail+='<h2>Final function states</h2>'+table(['Function','Target','Mean setting','Belief A','Belief G','Belief C','Commitment bounds'],[[i,summary['final_targets'][i],summary['final_mean_settings'][i],*belief,str(rows[-1]['bounds_after'][i])] for i,belief in enumerate(rows[-1]['beliefs_after'])])
        content=TEMPLATE.replace('<p><a href="research/research_report.html">Complete research report: all results, detailed analysis and individual run appendices →</a></p>','').replace('__DATA__',json.dumps(data,allow_nan=False).replace('</','<\\/')).replace('<h2>Across-world comparisons</h2>','<p><a href="../research_report.html">Return to complete study report</a></p>'+detail+'<h2>Across-world comparisons</h2>')
        (out/'runs'/f'{rid}.html').write_text(content)
    missing=sorted(expected-found);extra=sorted(found-expected) if expected else []
    incomplete=[str(p.parent.relative_to(root)) for p in root.glob('**/manifest.json') if not (p.parent/'complete.json').exists()]
    audit=dict(expected_jobs=len(expected) if expected else None,valid_completed=len(found),missing_jobs=missing,unexpected_jobs=extra,invalid_results=issues,incomplete_directories=incomplete,model_hashes=sorted(h for h in hashes if h),runtime_versions=[list(v) for v in sorted(versions_seen)],suite_summary=suite)
    # Never silently pool different model implementations.
    if len(hashes)>1:raise ValueError('Mixed model code hashes: report each version separately before comparing them.')
    aggregate=[];world_means={};world_rows=[]
    for arm,worlds in sorted(groups.items()):
        means={w:{k:float(np.mean([r[k] for r in reps if r[k] is not None])) if any(r[k] is not None for r in reps) else None for k in reps[0]} for w,reps in worlds.items()}
        world_means[arm]=means
        for w,m in means.items():world_rows.append(dict(family=arm[0],arm=arm[1],world=w,replicates=len(worlds[w]),**m))
        for metric in next(iter(means.values())):
            aggregate.append(dict(family=arm[0],arm=arm[1],metric=metric,runs=sum(map(len,worlds.values())),total_worlds=len(worlds),missing_runs=sum(r[metric] is None for reps in worlds.values() for r in reps),**stats([v[metric] for v in means.values()])))
    csv_write(out/'all_runs.csv',records);csv_write(out/'world_means.csv',world_rows);csv_write(out/'all_arm_statistics.csv',aggregate);csv_write(out/'interventions.csv',events);csv_write(out/'benchmark_audit.csv',benchmarks)
    atomic_json(out/'coverage_audit.json',audit);atomic_json(out/'metric_dictionary.json',DEFINITIONS)
    # Explicit scientifically chosen pairs only. No arbitrary lexical control.
    specs=json.loads(Path(contrast_path).read_text()) if contrast_path else [];contrasts=[]
    for spec in specs:
        a=(spec['family'],spec['reference']);b=(spec['family'],spec['treatment']);metric=spec['metric']
        if metric not in DEFINITIONS:raise ValueError(f'Unknown contrast metric: {metric}')
        ma=world_means.get(a,{});mb=world_means.get(b,{});shared=sorted(set(ma)&set(mb));diff=[mb[w][metric]-ma[w][metric] for w in shared if ma[w][metric] is not None and mb[w][metric] is not None]
        differences=[]
        if a in arm_jobs and b in arm_jobs:
            for section in ('world','config'):
                aj=arm_jobs[a][section];bj=arm_jobs[b][section]
                differences.extend(section+'.'+k for k in sorted(set(aj)|set(bj)) if aj.get(k)!=bj.get(k))
        contrasts.append(dict(**spec,changed_parameters='; '.join(differences),status='estimated' if diff else 'not estimable: missing arms or eligible observations',matched_worlds=len(shared),reference_worlds=len(ma),treatment_worlds=len(mb),**stats(diff)))
    csv_write(out/'planned_contrasts.csv',contrasts);atomic_json(out/'contrast_specification.json',specs)
    status='COMPLETE' if expected and not missing and not issues and not extra else 'PARTIAL / UNSPECIFIED DESIGN'
    methods=(f'This automatically generated report covers {len(records)} valid completed runs across {len(groups)} arms. Coverage status: {status}. '
      'Statistics first average nested replicas within each world, then weight independent worlds equally. Intervals are 95% percentile bootstrap intervals using 4,000 resamples and seed 4104. '
      'A single world has no uncertainty interval; fewer than ten worlds give fragile interval estimates. Intervals are exploratory and unadjusted for multiplicity. '
      'Missing values are excluded metric by metric, with denominators and missing counts reported. Settling times are conditional on observation; the settling-observed fraction reports censoring. '
      'Partial coverage can bias estimates, especially when failures depend on outcomes or nested replicas are missing. The older dashboard uses 90% intervals; this research bundle uses 95%.')
    limits=('The report is a reproducible descriptive analysis, not an automatically completed scientific paper. Causal claims require suitable controls; pre/post intervention changes mix treatment effects with ongoing learning and changes of world. '
      'Finite trajectories do not prove convergence, periodicity or exhaustive basin coverage. Raw aggregate above a feasible benchmark may indicate overload. Multi-start nonconcave benchmarks are best found unless independently certified. '
      'Period-zero baselines and unequal horizons must be compared explicitly. No p-values, significance claims, automatic hypothesis acceptance, or fabricated literature citations are produced. Select primary contrasts before confirmatory runs and address multiplicity in the final paper.')
    md=['# RSI v0.4 — experimental research report','', '## Study scope and methods','',methods,'','## Limitations and interpretation','',limits,'','## Coverage audit','',f'- Planned: {len(expected) if expected else "unspecified"}; valid complete: {len(found)}; missing: {len(missing)}; invalid: {len(issues)}; unexpected: {len(extra)}.','- Full audit: `coverage_audit.json`. Source hashes: `report_manifest.json`.','']
    body='<p class="note">'+html.escape(status)+' — all valid completed results are included, including adverse and null outcomes.</p>'+paragraph(methods)+'<h2>Coverage and reproducibility</h2>'+paragraph(f'Expected {len(expected) if expected else "unspecified"}; complete {len(found)}; missing {len(missing)}; invalid {len(issues)}; unexpected {len(extra)}.')+'<p><a href="coverage_audit.json">Full coverage audit</a> · <a href="report_manifest.json">Provenance and checksums</a> · <a href="research_report.md">Editable manuscript text</a> · <a href="all_arm_statistics.csv">All metric statistics</a> · <a href="all_runs.csv">Every run</a> · <a href="world_means.csv">World-level analysis data</a></p>'
    body+='<h2>Contents</h2><nav>'+ ' · '.join('<a href="#family-'+html.escape(f)+'">'+html.escape(f)+'</a>' for f in sorted(set(k[0] for k in groups)))+' · <a href="#comparisons">Comparisons</a> · <a href="#appendix">Every run</a></nav>'
    figure_rows=[]
    for family in sorted(set(k[0] for k in groups)):
        try:
            from .plots import plot_family_statistics
            plot_family_statistics(family,[r for r in aggregate if r['family']==family],out/'figures')
            figure_rows.append(dict(family=family,svg=f'figures/{family}.svg',png=f'figures/{family}.png',caption='All completed arms: world means and exploratory 95% bootstrap intervals. Single-world arms have no interval. Tail windows contain up to 20 observations. Compare configurations and feasibility before interpreting differences.'))
        except ImportError: break
    csv_write(out/'figure_index.csv',figure_rows)
    descriptions={(a['family'],a['name']):a for a in plan.get('arms',[])}
    for family in sorted(set(k[0] for k in groups)):
        body+='<h2 id="family-'+html.escape(family)+'">'+html.escape(family)+' — results and interpretation</h2>';md+=['## '+family+' — results and interpretation','']
        fig=next((f for f in figure_rows if f['family']==family),None)
        if fig:
            body+='<p><a href="'+fig['svg']+'">Publication figure (SVG)</a> · <a href="'+fig['png']+'">PNG</a></p><img style="max-width:100%" alt="'+family+' all-arm comparison" src="'+fig['svg']+'">'+paragraph(fig['caption'])
            md+=['!['+family+' all-arm comparison]('+fig['svg']+')','',fig['caption'],'']
        for arm in sorted(k for k in groups if k[0]==family):
            entries=[r for r in aggregate if (r['family'],r['arm'])==arm];lookup={r['metric']:r for r in entries};desc=descriptions.get(arm,{})
            narrative=(f"{arm[1]}: {entries[0]['runs']} runs across {entries[0]['total_worlds']} worlds. "
              f"Final Y = {fmt(lookup['final_Y']['mean'])}; final reward = {fmt(lookup['final_reward']['mean'])}; mean overload = {fmt(lookup['mean_overload']['mean'])}. "
              f"Tail target range = {fmt(lookup['tail_target_range']['mean'])}; observed outcome-settling fraction = {fmt(lookup['settling_observed']['mean'])}. "
              f"Maximum eligible identification error (averaged over worlds) = {fmt(lookup['max_valid_identification_error']['mean'])}. ")
            if lookup['mean_overload']['max']>1e-8:narrative+='Some runs overload the budget; raw-Y efficiency comparisons require qualification. '
            if lookup['skip_fraction']['mean'] is not None and lookup['skip_fraction']['mean']>.5:narrative+='More than half of scheduled turns are skipped on average; effective exploration is limited. '
            if entries[0]['total_worlds']<10:narrative+='This arm has fewer than ten worlds; treat its pattern as exploratory. '
            notes=desc.get('notes',[])
            body+='<h3>'+html.escape(arm[1])+'</h3>'+paragraph(desc.get('question',''))+paragraph(narrative)+paragraph('Design flags: '+'; '.join(notes) if notes else 'No predeclared design flag.')
            body+=table(['Metric','Worlds with data','Missing runs','Mean','Median','SD','Min','Max','95% low','95% high'],[[r[k] for k in ('metric','n','missing_runs','mean','median','sd','min','max','ci95_low','ci95_high')] for r in entries])
            md+=['### '+arm[1],'',desc.get('question',''),'',narrative,'','Design flags: '+('; '.join(notes) or 'none'),'', '| Metric | Worlds | Mean | 95% interval |','|---|---:|---:|---|']
            md += [f"| {r['metric']} | {r['n']} | {fmt(r['mean'])} | {fmt(r['ci95_low'])} to {fmt(r['ci95_high'])} |" for r in entries]
            md+=['','Configuration: `'+json.dumps(dict(world=arm_jobs[arm]['world'],config=arm_jobs[arm]['config']),sort_keys=True)+'`','']
    body+='<h2 id="comparisons">Explicit planned comparisons</h2>'+paragraph('Treatment minus reference, paired by world seed after averaging nested replicas. Seed matching does not itself establish exchangeability or a causal design. No multiplicity adjustment is claimed.')
    body+=table(list(contrasts[0]),[list(r.values()) for r in contrasts]) if contrasts else paragraph('No explicit contrast specification was supplied. No arbitrary control is selected. Supply --contrasts with family, reference, treatment and metric to generate matched-world differences and intervals.')
    md+=['## Explicit planned comparisons','',json.dumps(contrasts,indent=2) if contrasts else 'No explicit contrasts supplied. Use --contrasts before interpreting treatment effects.','']
    body+='<h2>Intervention audit</h2>'+paragraph(f'{len(events)} interventions logged. Pre/post windows contain up to 20 observations each; see interventions.csv for actual denominators and raw event details. These are descriptive changes across potentially different worlds.')
    body+='<h2 id="appendix">Complete run appendix</h2><p>Every valid completed run has a separate interactive trajectory, full scalar period table, metric table, benchmark history and reproduction manifest.</p><ul>'
    body+=''.join('<li><a href="runs/'+r['run_id']+'.html">'+html.escape('/'.join(map(str,(r['family'],r['arm'],r['world'],r['seed']))))+'</a></li>' for r in records)+'</ul>'
    md+=['## Complete run appendix','']+['- ['+'/'.join(map(str,(r['family'],r['arm'],r['world'],r['seed'])))+'](runs/'+r['run_id']+'.html)' for r in records]+['','## Metric dictionary','']+[f'- **{k}**: {v}' for k,v in DEFINITIONS.items()]
    body+='<h2>Metric dictionary</h2>'+table(['Metric','Definition'],DEFINITIONS.items())+'<h2>Discussion and limits</h2>'+paragraph(limits)
    body+='<h2>Integration into a research paper</h2>'+paragraph('Use the methods and per-arm results as editable source text. Cite run IDs and manifest hashes beside empirical claims. Include the full parameter catalog, coverage audit, exclusions and benchmark status in supplementary materials. Choose confirmatory contrasts, validate scientific interpretations, and add the manuscript’s theoretical context and references before submission. Print this HTML to PDF if a paginated review copy is needed.')
    (out/'research_report.html').write_text(page('RSI Functions v0.4 — complete experimental report',body));(out/'research_report.md').write_text('\n'.join(md)+'\n')
    for name in ('plan.json','suite_summary.json'):
        p=root/name
        if p.exists(): inputs.append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    source_hash=hashlib.sha256(b''.join((Path(__file__).parent/n).read_bytes() for n in ('research_report.py','analysis.py','plots.py'))).hexdigest()
    atomic_json(out/'report_manifest.json',dict(report_version=REPORT_VERSION,generated_at=datetime.now(timezone.utc).isoformat(),report_code_sha256=source_hash,python=platform.python_version(),numpy=np.__version__,input_root=str(root.resolve()),source_files=inputs,model_hashes=list(hashes),contrast_specification=specs,bootstrap=dict(resamples=4000,seed=4104,confidence=.95),coverage_status=status))
    print(f'Complete research bundle: {out}/research_report.html ({len(records)} individual appendices)')
    return audit
