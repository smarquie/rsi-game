"""Portable HTML report, CSV summaries, and empirical across-seed intervals."""
from collections import defaultdict
import csv
import html
import json
from pathlib import Path
import numpy as np


def summarize(rows):
    last=rows[-1]; accepted=[r for r in rows if r['accepted']]; hits=[r['diagnostic_hit'] for r in rows if r['diagnostic_hit'] is not None]
    w=np.array([r['W'] for r in rows]); s=np.array([r['score'] for r in rows]); plateau=best=0
    for row in rows:
        plateau=0 if row['accepted'] else plateau+1; best=max(best,plateau)
    corr=float(np.corrcoef(w,s)[0,1]) if np.std(w)>1e-12 and np.std(s)>1e-12 else None
    return dict(final_W=last['W'],final_Q=last['Q'],gain_W=last['W']-rows[0]['W_before'],mean_W=float(w.mean()),
                welfare_area=float(np.trapz(np.r_[rows[0]['W_before'],w])),final_score=last['score'],final_reference_score=last['reference_score'],
                final_anchor=last['protocol']['anchor'],final_separation=last['protocol']['separation'],final_rho_E=last['rho_E'],
                accepted_rate=len(accepted)/len(rows),false_accept_share=sum(r['false_accept'] for r in accepted)/len(accepted) if accepted else None,
                false_reject_rate=sum(r['false_reject'] for r in rows)/len(rows),diagnostic_hit_rate=float(np.mean(hits)) if hits else None,
                nonconverged_share=sum(not r['converged'] for r in rows)/len(rows),promotion_count=sum(r['promoted'] for r in rows),
                total_cycles=len(rows)+sum(r['promotion_trial_cycles'] for r in rows),max_rejection_plateau=best,score_welfare_correlation=corr,
                reversals_adjacent_epoch=sum(r['reversal_coordinates'] for r in rows))


def aggregate(values):
    x=np.array([v for v in values if v is not None],dtype=float)
    if not len(x): return dict(mean=None,low=None,high=None,n=0)
    return dict(mean=float(x.mean()),low=float(np.quantile(x,.05)),high=float(np.quantile(x,.95)),n=len(x))


def report(source,output):
    root=Path(source); groups=defaultdict(list); runs=[]
    for path in sorted(root.glob('study/E*/**/cycles.jsonl')):
        rows=[json.loads(line) for line in path.read_text().splitlines()]; parts=path.relative_to(root/'study').parts
        if not rows: continue
        experiment,arm,seed=parts[:3]; metrics=summarize(rows); groups[(experiment,arm)].append(metrics)
        runs.append(dict(name=f'{experiment} · {arm} · {seed}',metrics=metrics,rows=[{k:r[k] for k in ('t','Q','W','score','reference_score','protocol','rho_E','configuration','converged')} for r in rows]))
    summary=[]
    for (experiment,arm),items in groups.items():
        summary.append(dict(experiment=experiment,arm=arm,runs=len(items),metrics={k:aggregate([x[k] for x in items]) for k in items[0]}))
    out=Path(output); out.parent.mkdir(parents=True,exist_ok=True)
    (out.parent/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    with (out.parent/'summary.csv').open('w') as f:
        writer=csv.writer(f); writer.writerow(['experiment','arm','metric','mean','p05','p95','seeds'])
        for group in summary:
            for name,metric in group['metrics'].items(): writer.writerow([group['experiment'],group['arm'],name,metric['mean'],metric['low'],metric['high'],metric['n']])
    object_path=root/'default_object/object_analysis.json'
    obj=json.loads(object_path.read_text()) if object_path.exists() else {}
    exact=obj.get('exhaustive',{}); pure=exact.get('pure_equilibria',[]); attractors=exact.get('sweep_attractors',[])
    e5=[]
    for path in sorted(root.glob('study/E5/**/object_analysis.json')):
        data=json.loads(path.read_text()); ex=data.get('exhaustive',{})
        e5.append(dict(arm=path.parent.parent.name,Q=data['Q'],W=data['W'],pure_equilibria=len(ex.get('pure_equilibria',[])),
                       pure_PoA=ex.get('pure_price_of_anarchy'),cycles=sum(a['period']>1 for a in ex.get('sweep_attractors',[]))))
    audit_path=root/'analytical_audit.json'; audit=json.loads(audit_path.read_text()) if audit_path.exists() else {}
    study_manifest=root/'study/study_manifest.json'; manifest=json.loads(study_manifest.read_text()) if study_manifest.exists() else {'status':'Study incomplete at report generation'}
    payload=json.dumps(dict(runs=runs,summary=summary,object=obj,e5=e5,audit=audit,manifest=manifest),allow_nan=False).replace('</','<\\/')
    content=TEMPLATE.replace('__DATA__',payload)
    out.write_text(content)
    print(f'Report: {len(runs)} meta runs, {len(summary)} meta arms, {len(e5)} object regimes')

TEMPLATE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RSI Game · Findings</title>
<style>:root{font-family:system-ui,sans-serif;color:#202c3f;background:#f5f7fa}body{max-width:1160px;margin:auto;padding:45px 25px;line-height:1.65}h1{font-size:42px;line-height:1.15;letter-spacing:-1px;font-weight:600}h2{margin-top:45px;font-weight:600;font-size:25px}h3{font-size:18px}p{max-width:950px}.eyebrow{color:#237b74;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase}.lead{font-size:20px;color:#46566c}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.card,section.chart{background:white;border:1px solid #dce3ed;padding:22px;border-radius:12px}.value{font-size:30px;line-height:1.3;font-weight:600}.label{font-size:12px;color:#67758a}.note{border-left:4px solid #caa664;padding:8px 20px;background:#fff9ec}.good{border-left-color:#237b74;background:#eff9f6}table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}td,th{padding:10px 12px;border-bottom:1px solid #e3e8ef;text-align:left;vertical-align:top}th{background:#edf2f7;font-weight:600}.scroll{overflow-x:auto}select,input{padding:10px;border:1px solid #bac6d5;border-radius:6px;background:white;font:inherit;max-width:100%}select{margin:6px 14px 14px 0}svg{width:100%;height:auto}button{padding:10px 16px;border:0;border-radius:6px;background:#1c726d;color:white;cursor:pointer}code{font-size:13px;background:#e9edf4;padding:2px 5px;border-radius:3px}pre{white-space:pre-wrap;background:#182439;color:#edf3ff;padding:20px;border-radius:10px;font-size:12px}summary{cursor:pointer;font-weight:600}details{margin:18px 0}.muted{color:#67758a;font-size:13px}.legend{display:flex;gap:16px;font-size:12px;flex-wrap:wrap}.legend span:before{content:'●';color:var(--c);margin-right:6px}.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}a{color:#176f6a}footer{margin-top:60px;padding-top:25px;border-top:1px solid #d6dee9}@media(max-width:750px){.cards,.two{grid-template-columns:1fr 1fr}h1{font-size:32px}.two{grid-template-columns:1fr}}@media print{body{padding:0}details{display:block}select,button{display:none}}</style>
<div class="eyebrow">Serge Marquie · Model review & computational study · 1 October 2026</div>
<h1>A useful game of self-improvement.<br>A surprisingly sharp coordination problem.</h1>
<p class="lead">The central strength is the separation between true performance, self-evaluation, and the identity of the improver. The simulations expose those mechanisms, but the default object game is dominated by inactive review and budget thresholds.</p>
<div class="cards" id="cards"></div>
<p class="note"><strong>Scope of “all possible dynamics”.</strong> We enumerate every feasible action profile, every pure equilibrium, the global team optimum, and every attractor of the specified deterministic best-response sweep at each analyzed object configuration. Continuous capabilities, stochastic edits, alternative update schedules, mixed strategies, and strategic meta-policies are not exhaustively solved. The E1–E8 runs implement the draft’s greedy behavioral benchmark, not a Markov-perfect equilibrium.</p>
<h2>The main findings</h2><div id="findings"></div>
<div class="two"><div><h3>What works well in the design</h3><p>Sticky snapshots make evaluator drift an explicit design variable. Hidden-state production distinguishes wrong interpretation from downstream errors, and downstream repair avoids assuming a pure weakest-link production function. Editable evaluation makes reward distortion a consequence of selection rather than an imposed time trend.</p></div><div><h3>What I would change first</h3><p>Add a calibration in which critic-triggered revisions actually occur at equilibrium. Separate the cost of a long context from a hard feasibility threshold to see whether low-welfare equilibria survive. Preserve a fixed protected evaluation score in every experiment, and report welfare separately from success probability.</p></div></div>
<h2>Explore the simulated trajectories</h2><p id="coverage"></p><p class="muted">Single-run trajectories reveal mechanisms, not population effects. The tables use empirical 5th–95th percentiles across seeds; these are not confidence intervals for the mean. Three seeds are insufficient to establish a hump-shaped response, asymptotic erosion, or ignition.</p>
<section class="chart"><label for="run">Run</label><br><select id="run"></select><label for="view">View</label> <select id="view"><option value="outcome">Outcomes and yardsticks</option><option value="grounding">Grounding and correlation</option><option value="capability">Role capabilities</option></select><div class="legend" id="legend"></div><svg id="plot" viewBox="0 0 1050 360" role="img" aria-label="Research trajectories"></svg><p id="rundetail" class="muted"></p></section>
<h2>Experiment comparisons</h2><label for="experiment">Experiment</label> <select id="experiment"></select><label for="metric">Metric</label> <select id="metric"></select><div class="scroll"><table><thead><tr><th>Arm</th><th>Mean</th><th>Across-seed 90% interval</th><th>Seeds</th></tr></thead><tbody id="comparisons"></tbody></table></div>
<h2>Congestion regimes: exhaustive object analysis</h2><p class="muted">E5 changes private token cost κ while retaining the draft’s mission cost κT = 0.5. Price of anarchy below is the global team optimum minus the worst pure equilibrium’s welfare. No mixed-equilibrium price of anarchy is claimed.</p><div class="scroll"><table><thead><tr><th>Regime</th><th>Selected Q</th><th>Selected W</th><th>Pure equilibria</th><th>Pure PoA</th><th>Sweep cycles</th></tr></thead><tbody id="regimes"></tbody></table></div>
<h2>Mathematical claims that need qualification</h2><div class="scroll"><table><thead><tr><th>Claim</th><th>Assessment and repair</th></tr></thead><tbody>
<tr><td>Interpreter floor, Proposition 1</td><td>Valid when wrong-script repair is zero: W is absorbing and Q ≤ E[qI]. The implementation tests this invariant.</td></tr>
<tr><td>Correlated critic, Proposition 2</td><td>The weak inequality is valid. Strict loss additionally needs positive correct-state mass and at least one feasible revision after a flag. With L = 0 or no budget for revision, quality and tokens are unchanged by f.</td></tr>
<tr><td>Repair and congestion, Lemma 3 / Proposition 4</td><td>The two-stage cross-partial is 1 − η. Proposition 4 describes the stated common-load, no-repair surrogate, not the full sequential-load game. Discrete best responses and budget cliffs can defeat smooth intuition.</td></tr>
<tr><td>Weakest-link blindness, Proposition 5</td><td>Use failure-origin shares conditional on a perceived true failure in the attribution formula. Unconditional true-failure shares need not equal perceived-failure shares when W and D are detected at different rates. A high failure-origin count also need not identify the largest welfare gain from a capability edit. The critic never directly originates a 1→error transition, even when its policy is harmful.</td></tr>
<tr><td>No within-epoch cycles, Proposition 6</td><td>The strict-potential result requires exact evaluation, a fixed yardstick, and deterministic configuration-only selection. Warm-start selection and noisy acceptance invalidate that argument. The arbitrary evaluator-family cycle construction does not establish a cycle for the particular evaluator in equations 20–22.</td></tr>
<tr><td>Incumbent bias, Proposition 7</td><td>As written, changing cG also changes tE, so the proof cannot hold other evaluator terms fixed. Add fixed generator capability/detection power, or an explicit inequality comparing both effects. The audit provides a conditional algebraic example where greater capability distance lowers ρE but still raises the score because detection weakens.</td></tr>
<tr><td>Grounding erosion, Proposition 8</td><td>The derivatives are correct for a fixed agent and snapshot. Reaching exactly zero needs every remaining downward step, including a clipped final step, to beat δ. A positive margin can produce a positive-anchor plateau. Along agent edits the derivative’s coefficient also changes.</td></tr>
<tr><td>Measurement inversion, Corollary 9</td><td>The formula J = 1 − fE Q holds at the stated fully correlated limit. Acceptance still requires the resulting score gain to exceed δ. Defaults have ρE,0 = 0.9, so zero separation alone does not attain ρE = 1.</td></tr>
<tr><td>Greedy policy versus meta equilibrium</td><td>Γ = 0 removes continuation beyond the epoch; it does not make greedy one-step action selection optimal within a multi-cycle epoch. Label the simulator a behavioral benchmark throughout.</td></tr>
</tbody></table></div><details><summary>Numerical counterexamples and calibration audit</summary><pre id="audit"></pre></details>
<h2>Implementation decisions and limitations</h2><ul>
<li><strong>Initial-pass feasibility:</strong> the mandatory I,M,R,G,C pass must fit within B. Infeasible unilateral deviations are excluded; if growth makes even zero effort infeasible, the proposal is rejected. Beyond the fully feasible default grid this is a constrained/generalized policy game.</li>
<li><strong>Defaults retained:</strong> no automatic calibration or tuning to obtain a desired conclusion. The initial Q lies in the requested range; a 10% generator-capability gain, including overhead growth, improves welfare by more than 0.005.</li>
<li><strong>Equilibrium reporting:</strong> a logit fallback is marked nonconverged and carries a unilateral-deviation regret. A modal logit profile is not a Nash equilibrium. Multi-start diagnostics do not establish uniqueness. Coordinate-ascent welfare gaps are labeled lower bounds; only full enumeration certifies pure price of anarchy.</li>
<li><strong>Queued evaluation changes:</strong> accepted changes are judged against the active protocol. At handover, the latest accepted value for each coordinate is applied. For K = ∞, deferred changes never activate. Clipped live-critic separation edits pay only for the actual change.</li>
<li><strong>Gated promotion:</strong> one independent Hign-cycle trial per improver; freeze snapshot refresh during each trial, compare endpoint scores under the incumbent evaluator, and divide the difference by Hign. Tests are discarded and their cycle counts are logged. The draft does not specify repeated-trial averaging; this choice is explicit.</li>
<li><strong>Capability frontier:</strong> cmax reduces proposal drift; it is not a hard cap, because equation 26 uses unbounded Gaussian log-edits.</li>
<li><strong>Reproducibility:</strong> separate seeded streams for diagnosis, proposals, measurement, and promotion trials; exact immutable configuration cache keys avoid rounding collisions. JSON configuration replaces YAML to keep dependencies minimal.</li>
<li><strong>Study limits:</strong> three seeds and 100 cycles per meta arm, rather than the paper’s 50 × 200. All E1–E8 arms are runnable at full scale. Some higher-cost diagnostics remain approximations: local team search, multi-start multiplicity, and adjacent-epoch coordinate reversal counts. The full strategic meta-game, mixed equilibria, history-dependent policies, and real-model calibration remain research extensions.</li>
</ul>
<h2>Default equilibria and attraction basins</h2><p class="muted">Each row is a distinct action profile; some profiles are outcome-equivalent. Basin shares are fractions of a uniform grid of starting profiles, not probabilities over actual deployments. All tie decisions retain the current action when it is optimal.</p><details><summary>Show all equilibria</summary><div class="scroll"><table><thead><tr><th>Profile indices [I,M,R,G,C]</th><th>Welfare</th><th>Basin size</th><th>Basin share</th></tr></thead><tbody id="equilibria"></tbody></table></div></details>
<h2>How to reproduce</h2><pre>.venv/bin/python main.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m rsi_game analyze --attractors --output results/default_object
.venv/bin/python research.py --seeds 3 --cycles 100 --workers 4
.venv/bin/python audit.py
.venv/bin/python -m rsi_game report

# Full paper-scale meta study:
.venv/bin/python research.py --seeds 50 --cycles 200 --workers 4 --output results/full_scale</pre>
<footer><p>Source: Serge Marquie, <em>A Two-Level Game of a Self-Improving Agent</em>, working draft v0.1, 1 October 2026. Implemented against equations 1–27 and algorithms 1–3. Assessment of novelty relative to the cited literature is outside this computational review; bibliographic claims were not independently verified.</p><p class="muted" id="manifest"></p></footer>
<script>const D=__DATA__;const $=id=>document.getElementById(id),fmt=x=>x==null?'—':Number(x).toFixed(4),esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ex=D.object.exhaustive||{},eq=ex.pure_equilibria||[],at=ex.sweep_attractors||[],top=[...at].sort((a,b)=>b.basin_profiles-a.basin_profiles),share=top.slice(0,2).reduce((n,a)=>n+a.basin_profiles,0)/(ex.feasible_profiles||1);
$('cards').innerHTML=[[ex.profiles?.toLocaleString()||'—','Action profiles enumerated'],[eq.length,'Default pure equilibria'],[fmt(ex.team_optimum?.welfare),'Global team welfare'],[fmt(ex.pure_price_of_anarchy),'Worst-pure welfare gap']].map(([v,k])=>`<div class="card"><div class="value">${v}</div><div class="label">${k}</div></div>`).join('');
$('findings').innerHTML=`<p><strong>Multiple starts missed substantial multiplicity.</strong> Low, high, and canonical starts find the usual equilibrium, yet enumeration finds ${eq.length} pure equilibria. Under the fixed I→M→R→G→C sweep, the two largest basins cover ${(share*100).toFixed(2)}% of all starts. ${at.filter(a=>a.period>1).length} nontrivial sweep cycles occur at the default configuration.</p><p><strong>Coordination has value.</strong> The usual equilibrium has Q = ${fmt(D.object.Q)}, W = ${fmt(D.object.W)}, and expected token use ${fmt(D.object.tokens)}. Global team welfare is ${fmt(ex.team_optimum?.welfare)}. The worst pure equilibrium has W = ${eq.length?fmt(Math.min(...eq.map(a=>a.welfare))):'—'}. The selected-equilibrium loss and worst-equilibrium price of anarchy are different quantities.</p><p><strong>Default review is inactive.</strong> The audit finds no executed revision rounds at any default pure equilibrium. Some equilibria turn off flagging; others make revision too costly to fit. This calls for a separate active-review calibration before interpreting hypotheses about improved critics.</p>`;
$('coverage').textContent=`${D.runs.length} completed meta runs across ${D.summary.length} arms, plus ${D.e5.length} exhaustively enumerated congestion regimes. Study settings: ${D.manifest.seeds||'pending'} seeds × ${D.manifest.cycles||'pending'} cycles per meta arm.`;
D.runs.forEach((r,i)=>$('run').add(new Option(r.name,i)));const experiments=[...new Set(D.summary.map(s=>s.experiment))];experiments.forEach(e=>$('experiment').add(new Option(e,e)));if(D.summary.length)Object.keys(D.summary[0].metrics).forEach(k=>$('metric').add(new Option(k.replaceAll('_',' '),k)));
function compare(){const exp=$('experiment').value,k=$('metric').value;$('comparisons').innerHTML=D.summary.filter(s=>s.experiment===exp).map(s=>{let m=s.metrics[k];return `<tr><td>${esc(s.arm)}</td><td>${fmt(m.mean)}</td><td>[${fmt(m.low)}, ${fmt(m.high)}]</td><td>${m.n}</td></tr>`}).join('');}
const palette=['#16857c','#426ace','#b7792b','#8b54b5','#b34265'];function plot(){const r=D.runs[+$('run').value];if(!r)return;let keys,names,values;if($('view').value==='outcome'){keys=['Q','W','score','reference_score'];names=['True quality','Mission welfare','Current score','Fixed reference score'];values=r.rows.map(x=>keys.map(k=>x[k]));}else if($('view').value==='grounding'){names=['Anchor share','Evaluator separation','Evaluator correlation'];values=r.rows.map(x=>[x.protocol.anchor,x.protocol.separation,x.rho_E]);}else{names=['Interpreter','Memory','Reasoner','Generator','Critic'];values=r.rows.map(x=>x.configuration.c);}const all=values.flat(),lo=Math.min(0,...all)-.02,hi=Math.max(...all)+.04,y=v=>310-(v-lo)/(hi-lo)*275,x=i=>60+i/Math.max(1,values.length-1)*955;let svg='';for(let j=0;j<=5;j++){const v=lo+(hi-lo)*j/5;svg+=`<line x1="60" x2="1015" y1="${y(v)}" y2="${y(v)}" stroke="#e2e8f0"/><text x="48" y="${y(v)+4}" fill="#63748a" text-anchor="end" font-size="12">${v.toFixed(2)}</text>`;}names.forEach((k,j)=>svg+=`<polyline fill="none" stroke="${palette[j]}" stroke-width="2.3" points="${values.map((v,i)=>`${x(i)},${y(v[j])}`).join(' ')}"/>`);svg+=`<text x="60" y="333" fill="#63748a" font-size="12">1</text><text x="1015" y="333" text-anchor="end" fill="#63748a" font-size="12">${values.length}</text><text x="525" y="353" text-anchor="middle" fill="#63748a" font-size="12">Improvement cycle (post-decision)</text>`;$('plot').innerHTML=svg;$('legend').innerHTML=names.map((n,i)=>`<span style="--c:${palette[i]}">${n}</span>`).join('');$('rundetail').textContent=`Final welfare ${fmt(r.metrics.final_W)} · Welfare gain ${fmt(r.metrics.gain_W)} · Accepted ${(100*r.metrics.accepted_rate).toFixed(1)}% · Nonconverged profiles ${(100*r.metrics.nonconverged_share).toFixed(1)}%`;}
$('run').onchange=plot;$('view').onchange=plot;$('experiment').onchange=compare;$('metric').onchange=compare;plot();compare();
$('regimes').innerHTML=D.e5.map(r=>`<tr><td>${esc(r.arm)}</td><td>${fmt(r.Q)}</td><td>${fmt(r.W)}</td><td>${r.pure_equilibria}</td><td>${fmt(r.pure_PoA)}</td><td>${r.cycles}</td></tr>`).join('');
$('equilibria').innerHTML=[...eq].sort((a,b)=>b.welfare-a.welfare).map(r=>{const a=at.find(a=>a.period===1&&JSON.stringify(a.profiles[0])===JSON.stringify(r.profile));return `<tr><td>${JSON.stringify(r.profile)}</td><td>${fmt(r.welfare)}</td><td>${a?.basin_profiles||0}</td><td>${(100*(a?.basin_profiles||0)/(ex.feasible_profiles||1)).toFixed(3)}%</td></tr>`}).join('');
const {equilibria,...audit}=D.audit;$('audit').textContent=JSON.stringify(audit,null,2);$('manifest').textContent=JSON.stringify(D.manifest);</script></html>'''
