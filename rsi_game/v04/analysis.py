"""World-level aggregation, paired contrasts, portable report and standard plots."""
from collections import defaultdict
from pathlib import Path
import csv
import json
import numpy as np
from .storage import atomic_json


def interval(values,seed=4104):
    x=np.array(values,dtype=float)
    if not len(x): return dict(mean=None,low=None,high=None,worlds=0)
    if len(x)==1:return dict(mean=float(x[0]),low=None,high=None,worlds=1)
    rng=np.random.default_rng(seed);means=x[rng.integers(0,len(x),size=(2000,len(x)))].mean(axis=1)
    return dict(mean=float(x.mean()),low=float(np.quantile(means,.05)),high=float(np.quantile(means,.95)),worlds=len(x))


def metrics(summary,rows):
    keys=('initial_Y','final_Y','final_reward','improvement','gap_to_best_found','settling_period','total_overload','skipped_turns','jump_events','bound_violations','tail_target_range','target_path_length')
    data={k:summary[k] for k in keys};data['within_one_percent_best']=float(summary['within_one_percent_best'])
    data['mean_absolute_staleness']=float(np.mean([abs(e) for r in rows for e in r['staleness_error']]))
    fits=[v for r in rows for v in r['updates'].values() if v.get('updated')]
    data['max_curvature_fit_error']=max((abs(v['C_error']) for v in fits),default=None)
    data['max_slope_fit_error']=max((abs(v['G_error']) for v in fits),default=None)
    verified=[v for v in fits if v['exact_identification_conditions']]
    data['max_valid_identification_error']=max((max(abs(v['C_error']),abs(v['G_error'])) for v in verified),default=None)
    data['max_exploration_formula_error']=max((abs(r['exploration_effect']-r['predicted_exploration_effect']) for r in rows if r['exploration_formula_applicable']),default=None)
    return data


def report(root,output=None,max_trajectories=96,contrasts=None):
    root=Path(root);output=Path(output) if output else root/'report.html';output.parent.mkdir(parents=True,exist_ok=True)
    from .research_report import build
    audit=build(root,output.parent/'research',metrics,contrasts)
    excluded={r['path'] for r in audit['invalid_results']}
    groups=defaultdict(lambda:defaultdict(list));runs=[];catalog=[];seen_arms=set()
    for complete in sorted(root.glob('**/complete.json')):
        folder=complete.parent
        if str(folder.relative_to(root)) in excluded: continue
        manifest=json.loads((folder/'manifest.json').read_text());summary=json.loads((folder/'summary.json').read_text())
        rows=[json.loads(line) for line in (folder/'periods.jsonl').read_text().splitlines()]
        job=manifest['job'];key=(job['family'],job['arm']);world=job['world_seed'];values=metrics(summary,rows)
        groups[key][world].append(values);catalog.append(dict(family=key[0],arm=key[1],world=world,seed=job['seed'],**values))
        # At most one displayed trajectory per arm; stats always use all runs.
        if key not in seen_arms and len(runs)<max_trajectories:
            versions=json.loads((folder/'benchmarks.json').read_text())
            runs.append(dict(name='/'.join((key[0],key[1],f'world{world}',f'seed{job["seed"]}')),summary=summary,
                job=job,benchmarks=versions,
                rows=[{k:r[k] for k in ('period','mean_Y','reward','price','overload','mean_spending','mean_settings','targets','staleness_error','exploration_effect','predicted_exploration_effect','best_found_Y','skipped','fast_status')} for r in rows]))
            seen_arms.add(key)
    aggregate=[];world_means={}
    for (family,arm),worlds in sorted(groups.items()):
        keys=next(iter(worlds.values()))[0].keys();means={}
        for world,replicates in worlds.items():
            means[world]={k:float(np.mean([r[k] for r in replicates if r[k] is not None])) if any(r[k] is not None for r in replicates) else None for k in keys}
        world_means[(family,arm)]=means
        aggregate.append(dict(family=family,arm=arm,worlds=len(worlds),runs=sum(map(len,worlds.values())),
            metrics={k:interval([v[k] for v in means.values() if v[k] is not None]) for k in keys}))
    contrasts=[]
    for family in sorted({k[0] for k in groups}):
        controls=sorted(k for k in groups if k[0]==family);reference=controls[0];base=world_means[reference]
        for key in controls[1:]:
            values=world_means[key];common=sorted(set(base)&set(values))
            contrasts.append(dict(family=family,reference=reference[1],arm=key[1],metric='final_Y',
                **interval([values[w]['final_Y']-base[w]['final_Y'] for w in common])))
    atomic_json(output.parent/'aggregate.json',aggregate);atomic_json(output.parent/'paired_contrasts.json',contrasts)
    if catalog:
        with (output.parent/'run_summary.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(catalog[0]));writer.writeheader();writer.writerows(catalog)
    with (output.parent/'aggregate.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['family','arm','metric','mean','ci90_low','ci90_high','independent_worlds','runs'])
        for arm in aggregate:
            for metric,value in arm['metrics'].items():writer.writerow([arm['family'],arm['arm'],metric,value['mean'],value['low'],value['high'],value['worlds'],arm['runs']])
    plan_path=root/'plan.json';plan=json.loads(plan_path.read_text()) if plan_path.exists() else {}
    suite=root/'suite_summary.json';suite=json.loads(suite.read_text()) if suite.exists() else {}
    data=dict(runs=runs,aggregate=aggregate,contrasts=contrasts,count=len(catalog),planned=plan.get('job_count'),
        preset=plan.get('preset','single'),notes=[dict(family=a['family'],arm=a['name'],notes=a['notes']) for a in plan.get('arms',[]) if a['notes']],suite=suite)
    output.write_text(TEMPLATE.replace('__DATA__',json.dumps(data,allow_nan=False).replace('</','<\\/')))
    try:
        from .plots import plot_runs
        plot_runs(runs[:12],output.parent/'figures')
    except ImportError:
        print('Interactive report created. Install the reports extra for standalone matplotlib figures.')
    print(f'{output}: {len(catalog)} completed runs, {len(aggregate)} arms; {len(runs)} displayed trajectories')

TEMPLATE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RSI Functions v0.4 · Research</title>
<style>:root{font-family:system-ui,sans-serif;background:#f3f6fa;color:#1a2b42}body{max-width:1180px;margin:auto;padding:40px 25px;line-height:1.65}h1{font-size:38px;line-height:1.2}h2{margin-top:35px;font-size:24px}.tag{font-size:12px;color:#087c75;letter-spacing:2px;text-transform:uppercase}.note{padding:18px;border-left:4px solid #ca9952;background:#fff9ec}section{border:1px solid #dce4ed;background:#fff;padding:24px;border-radius:12px;margin:20px 0}select{max-width:100%;padding:8px;border:1px solid #b5c4d4;border-radius:5px;font:inherit;margin:8px 14px 10px 0}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:9px;text-align:left;border-bottom:1px solid #dde5ee}th{background:#edf2f7}.scroll{overflow:auto}svg{width:100%;height:auto}.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px}.legend span:before{content:'●';color:var(--c);margin-right:5px}pre{white-space:pre-wrap;background:#17273c;color:#fff;padding:18px;border-radius:8px;font-size:12px}.muted{color:#5d6e83;font-size:13px}summary{cursor:pointer;font-weight:600}a{color:#087c75}</style>
<div class="tag">Serge Marquie · Functions game · v0.4</div><h1>Decentralized learning under a shared budget</h1><p id="coverage"></p>
<p class="note"><strong>Read the scope before interpreting a gap.</strong> Indefinite-world optima are best found by multi-start SLSQP, not certified global optima. The optional branch-and-bound command reports an explicit remaining gap. Finite-width targets need not be budget-feasible; overload may make raw outcomes incomparable with the feasible team benchmark. This report does not classify a short transient as a proven fixed point or cycle.</p>
<p><a href="research/research_report.html">Complete research report: all results, detailed analysis and individual run appendices →</a></p><h2>Trajectories</h2><section><label for="run">Run</label><br><select id="run"></select><label for="view">View</label><select id="view"><option value="Y">Outcomes and benchmarks</option><option value="q">Settings and targets</option><option value="price">Price and overload</option><option value="belief">Absolute belief staleness</option><option value="exploration">Exploration effect: actual vs predicted</option></select><div class="legend" id="legend"></div><svg viewBox="0 0 1100 380" id="chart" role="img" aria-label="Model trajectories"></svg><p id="detail" class="muted"></p><details><summary>Run configuration and benchmark qualifications</summary><pre id="configuration"></pre></details></section>
<h2>Across-world comparisons</h2><p class="muted">Nested schedule/intervention replicas are averaged within each world first. Intervals are percentile-bootstrap 90% confidence intervals over independent world means. A single-world smoke run has no uncertainty interval. No multiple-comparison adjustment is claimed; preselect confirmatory contrasts before a large study.</p><label for="family">Family</label><select id="family"></select><label for="metric">Metric</label><select id="metric"></select><div class="scroll"><table><thead><tr><th>Arm</th><th>Mean</th><th>90% CI</th><th>Worlds</th><th>Runs</th></tr></thead><tbody id="comparison"></tbody></table></div>
<h2>Design flags</h2><div id="flags"></div><h2>Interpretation guide</h2><ul>
<li><strong>Identification:</strong> exact curvature/slope recovery requires nonzero dither, the frequency conditions, a fixed free-function background, and a raw quadratic aggregate. Adaptive clearing and finite-horizon mixtures can break the fixed-background assumption.</li>
<li><strong>Learning versus feasibility:</strong> raw Y, penalized reward, spending and overload are distinct series. A lower reward can reflect price instability or a infeasible exploration floor even if the fitted quadratic is exact.</li>
<li><strong>Traps:</strong> nearest stationary candidate is a distance diagnostic, not proof of basin membership. Use longer runs, residual checks, multiple starts and the two-dimensional basin command.</li>
<li><strong>Convergence:</strong> tail target range and settling time are finite-horizon diagnostics. Fixed-multiplier idealized tests differ from the finite-width, changing-price process.</li>
<li><strong>Outside changes:</strong> the invisible construction preserves slices through the chosen target. It need not preserve observations under finite-width commitments, shifted boundary centers, or changing backgrounds.</li>
<li><strong>Statistical unit:</strong> the baseline is deterministic conditional on the world. Changing only a seed does not create independent evidence. Random schedules and outside interventions supply nested randomness when enabled.</li>
</ul><h2>Saved artifacts</h2><p>Use <code>aggregate.csv</code>, <code>run_summary.csv</code> and <code>paired_contrasts.json</code> alongside the complete per-run JSONL/CSV/Parquet records. The contrasts file compares each arm with the lexicographically first completed arm in its family on shared world seeds; this is descriptive, not a claim that this is the scientifically preferred control. Standalone SVG/PNG plots for up to twelve representative runs are under <code>figures/</code>.</p>
<details><summary>Completion and failure audit</summary><pre id="audit"></pre></details>
<script>const D=__DATA__,$=id=>document.getElementById(id),fmt=x=>x==null?'—':Number(x).toFixed(5),esc=x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
$('coverage').textContent=`${D.count} completed runs / ${D.planned??'unspecified'} planned · ${D.aggregate.length} arms · preset ${D.preset}. Showing ${D.runs.length} representative trajectories.`;
D.runs.forEach((r,i)=>$('run').add(new Option(r.name,i)));[...new Set(D.aggregate.map(a=>a.family))].forEach(f=>$('family').add(new Option(f,f)));if(D.aggregate.length)Object.keys(D.aggregate[0].metrics).forEach(k=>$('metric').add(new Option(k.replaceAll('_',' '),k)));
const colors=['#137f77','#426cce','#b17c2d','#9453b1','#bc4963','#4b8da5','#857c41','#283955','#bf885c','#72897a','#bb636d','#5d8db4'];
function plot(){const run=D.runs[+$('run').value];if(!run)return;const rows=run.rows,n=rows[0].mean_settings.length;let names,series,dashes=[];switch($('view').value){case 'q':names=[...Array(n)].map((_,i)=>'q'+(i+1)).concat([...Array(n)].map((_,i)=>'target'+(i+1)));series=rows.map(r=>r.mean_settings.concat(r.targets));dashes=names.map((_,i)=>i>=n);break;case 'price':names=['Price','Overload'];series=rows.map(r=>[r.price,r.overload]);break;case 'belief':names=[...Array(n)].map((_,i)=>'|e'+(i+1)+'|');series=rows.map(r=>r.staleness_error.map(Math.abs));break;case 'exploration':names=['Realized exploration effect','Quadratic prediction'];series=rows.map(r=>[r.exploration_effect,r.predicted_exploration_effect]);break;default:names=['Raw mean Y','Penalized reward','Team best found','Ignore interactions','Informed free'];series=rows.map(r=>{const b=[...run.benchmarks].reverse().find(b=>b.period<=r.period).benchmarks;return[r.mean_Y,r.reward,r.best_found_Y,b.ignoring_interactions.Y,b.informed_free.Y]});}
const all=series.flat(),min=Math.min(...all),max=Math.max(...all),pad=Math.max((max-min)*.1,.01),low=min-pad,high=max+pad;const y=v=>320-(v-low)/(high-low)*285,x=i=>70+i/Math.max(1,rows.length-1)*1000;let svg='';for(let j=0;j<=5;j++){const v=low+(high-low)*j/5;svg+=`<line x1="70" x2="1070" y1="${y(v)}" y2="${y(v)}" stroke="#e2e8ef"/><text x="58" y="${y(v)+4}" text-anchor="end" font-size="12" fill="#63748a">${v.toFixed(3)}</text>`;}names.forEach((name,j)=>{svg+=`<polyline fill="none" stroke="${colors[j%colors.length]}" stroke-width="2" ${dashes[j]?'stroke-dasharray="5 4"':''} points="${series.map((s,i)=>`${x(i)},${y(s[j])}`).join(' ')}"/>`});svg+=`<text x="70" y="342" fill="#63748a" font-size="12">0</text><text x="1070" y="342" text-anchor="end" fill="#63748a" font-size="12">${rows.at(-1).period}</text><text x="550" y="370" text-anchor="middle" fill="#63748a" font-size="12">Review period</text>`;$('chart').innerHTML=svg;$('legend').innerHTML=names.map((n,j)=>`<span style="--c:${colors[j%colors.length]}">${n}${dashes[j]?' (dashed)':''}</span>`).join('');$('detail').textContent=`Final mean Y ${fmt(run.summary.final_Y)} · total overload ${fmt(run.summary.total_overload)} · skipped turns ${run.summary.skipped_turns} · actual T ${run.summary.actual_T}`;$('configuration').textContent=JSON.stringify({job:run.job,summary:run.summary},null,2);}
function compare(){const family=$('family').value,metric=$('metric').value;$('comparison').innerHTML=D.aggregate.filter(a=>a.family===family).map(a=>{let v=a.metrics[metric];return `<tr><td>${esc(a.arm)}</td><td>${fmt(v.mean)}</td><td>${v.low==null?'not estimated':`[${fmt(v.low)}, ${fmt(v.high)}]`}</td><td>${v.worlds}</td><td>${a.runs}</td></tr>`}).join('');}
$('run').onchange=plot;$('view').onchange=plot;$('family').onchange=compare;$('metric').onchange=compare;plot();compare();$('flags').innerHTML=D.notes.length?'<ul>'+D.notes.map(a=>`<li><strong>${esc(a.family+'/'+a.arm)}:</strong> ${a.notes.map(esc).join('; ')}</li>`).join('')+'</ul>':'No design flags.';$('audit').textContent=JSON.stringify(D.suite,null,2);</script></html>'''
