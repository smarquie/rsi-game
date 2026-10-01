"""Two-timescale learning process and complete, versioned diagnostics."""
from dataclasses import asdict
import numpy as np
from .config import Config
from .function_state import FunctionState
from .explore import frequencies,executions,schedule,amplitude,path,nonresonant
from .period import execute
from .review import review
from .benchmarks import benchmark_bundle,slice_residual,idealized
from .outside import intervene


def simulate(world,config=Config(),seed=0,benchmark_provider=None):
    config.validate_world(world); n=world.n; T=executions(n,config.T,config.frequencies)
    freq=frequencies(n,config.frequencies); streams=np.random.SeedSequence([seed,4104]).spawn(2)
    schedule_rng,outside_rng=[np.random.default_rng(s) for s in streams]
    states=[FunctionState(np.array((0.,config.g0,0.)),0.,(0.,world.qbar)) for _ in range(n)]
    provider=benchmark_provider or (lambda w:benchmark_bundle(w,config.multistarts))
    benchmarks=provider(world); versions=[dict(period=0,world=world.to_dict(),benchmarks=benchmarks)]
    rows=[]; execution_records=[]; previous_Y=0.; initial_world=world
    for r in range(config.periods+1):
        outside_event=None
        if r==config.outside_period and config.outside_kind!='none':
            targets=np.array([s.target for s in states]); old=world
            world=intervene(world,config.outside_kind,targets,outside_rng,config)
            for s in states: s.identification_valid=False
            benchmarks=provider(world); versions.append(dict(period=r,world=world.to_dict(),benchmarks=benchmarks))
            outside_event=dict(kind=config.outside_kind,old_world_hash=old.hash,new_world_hash=world.hash,
                target_Y_change=float(world.Y(targets)-old.Y(targets)),target_gradient_change=(world.grad(targets)-old.grad(targets)).tolist())
            if config.outside_relocate:
                relocation=benchmarks['team']['best']['q']
                for i,s in enumerate(states):
                    s.target=relocation[i]; s.bounds=(max(0.,s.target-config.w_min/2),min(world.qbar,s.target+config.w_min/2))
                outside_event['informed_relocation']=relocation
        planned=schedule(r,n,config.k,config.schedule,schedule_rng); paths={}; skipped=[]
        actual_k=n if config.schedule=='all' else config.k
        for i,s in enumerate(states):
            s.mode='free'; s.amplitude=0.
            if i in planned:
                a=amplitude(s.belief[2],previous_Y,s.scale,actual_k,config,world.qbar)
                if a==0: skipped.append(i)
                else:
                    values,z=path(s.target,a,freq[i],T,world.qbar)
                    paths[i]=values; s.center=z; s.amplitude=a; s.bounds=(z-a,z+a); s.mode='exploring'
        beliefs=np.array([s.belief.copy() for s in states]); bounds=np.array([s.bounds for s in states])
        before_valid=[s.identification_valid for s in states]
        targets_before=np.array([s.target for s in states]); contexts=[None if s.context is None else s.context.copy() for s in states]
        result=execute(world,beliefs,bounds,paths,T,config)
        centers=result['q'].mean(axis=0); true_coeff=np.array([world.local_coeffs(i,centers) for i in range(n)])
        stale=beliefs[:,1]-true_coeff[:,1]
        context_bounds=[]; context_formula=[]
        for i,ctx in enumerate(contexts):
            others=np.arange(n)!=i
            if ctx is None: context_bounds.append(None); context_formula.append(None)
            else:
                context_bounds.append(float(2*np.sum(abs(np.array(world.C)[i,others]))*np.max(abs(ctx[others]-centers[others]))) if n>1 else 0.)
                context_formula.append(float(2*np.array(world.C)[i,others]@(ctx[others]-centers[others])))
        updates={}
        if r==0:
            for i,s in enumerate(states): s.target=float(centers[i])
            if config.initial_targets is not None:
                for i,s in enumerate(states):
                    s.target=float(config.initial_targets[i]); s.bounds=(max(0.,s.target-config.w_min/2),min(world.qbar,s.target+config.w_min/2))
        else:
            for i in paths:
                s=states[i]
                # No World, other states, or diagnostic contexts enter this API.
                update=review(s,result['q'][:,i],result['Y'],result['price'],world.gamma[i],world.w[i],config,world.qbar,previous_Y,r)
                if update['updated']:
                    fitted=np.array(update['fitted']); update['G_error']=float(fitted[1]-true_coeff[i,1]); update['C_error']=float(fitted[2]-true_coeff[i,2])
                    update['center_slope']=float(fitted[1]+2*fitted[2]*centers[i]); update['true_partial']=float(world.grad(centers)[i])
                    update['true_lagrangian_partial']=float(world.grad(centers)[i]-result['price']/world.w[i]*world.gamma[i]/(1-centers[i]))
                    update['exact_identification_conditions']=bool(result['free_background_constant'] and (len(paths)==1 or nonresonant([freq[j] for j in paths])) and config.within_period=='fixed')
                    s.context=centers.copy(); s.identification_valid=update['exact_identification_conditions'] and config.phi_mem==1
                updates[str(i)]=update
        targets=np.array([s.target for s in states]); best=np.array(benchmarks['team']['best']['q'])
        locals_=benchmarks['team']['validated_stationary_points']; distances=[float(np.max(abs(targets-np.array(x['q'])))) for x in locals_]
        prediction=float(.5*sum(world.C[i][i]*states[i].amplitude**2 for i in paths))
        loss=float(result['mean_Y']-world.Y(centers))
        row=dict(period=r,world_hash=world.hash,price=result['price'],mean_Y=result['mean_Y'],reward=result['reward'],target_Y=float(world.Y(targets)),
            mean_settings=centers.tolist(),targets_before=targets_before.tolist(),targets=targets.tolist(),target_spending=float(world.spend(targets)),
            mean_spending=float(result['spending'].mean()),overload=result['overload'],explorers=list(paths),planned_explorers=planned,skipped=skipped,
            beliefs_before=beliefs.tolist(),beliefs_after=[s.belief.tolist() for s in states],bounds_during=bounds.tolist(),bounds_after=[list(s.bounds) for s in states],
            amplitudes=[s.amplitude for s in states],scales=[s.scale for s in states],true_local_coefficients=true_coeff.tolist(),staleness_error=stale.tolist(),
            context_staleness_bound=context_bounds,context_staleness_formula=context_formula,
            context_identity_valid=before_valid,
            updates=updates,exploration_effect=loss,predicted_exploration_effect=prediction,
            exploration_formula_applicable=bool(result['free_background_constant'] and len(set(freq[j] for j in paths))==len(paths)),
            disruption_allowance=float(config.eps_dis*abs(previous_Y)),
            at_lower_bound=np.mean(abs(result['q']-bounds[:,0])<1e-8,axis=0).tolist(),at_upper_bound=np.mean(abs(result['q']-bounds[:,1])<1e-8,axis=0).tolist(),
            distance_to_best_found=float(np.max(abs(targets-best))),nearest_stationary_index=int(np.argmin(distances)) if distances else None,
            distance_to_stationary=min(distances) if distances else None,best_found_Y=benchmarks['team']['best']['Y'],global_certified=benchmarks['team']['global_certified'],
            theoretical_spending=result['theoretical_spending'],complementarity_residual=result['complementarity'],fast_status=result['fast_status'],
            jump_events=result['jump_events'],bound_violations=result['bound_violations'],outside_event=outside_event)
        rows.append(row)
        if config.log_executions:
            execution_records.append(dict(period=r,q=result['q'].tolist(),Y=result['Y'].tolist(),spending=result['spending'].tolist(),prices=result['prices'].tolist()))
        previous_Y=result['mean_Y']
    final=rows[-1]; values=np.array([x['mean_Y'] for x in rows]); tolerance=.01*max(abs(values[-1]),1e-12)
    # Require at least 20 observed periods; the final observation alone cannot establish settling.
    settling=next((i for i in range(max(0,len(values)-19)) if np.all(abs(values[i:]-values[-1])<=tolerance)),None)
    total_steps=float(sum(np.linalg.norm(np.array(b['targets'])-a['targets']) for a,b in zip(rows,rows[1:])))
    tail=np.array([x['targets'] for x in rows[-min(20,len(rows)):]])
    mu=final['price']/world.w[0]
    residual=slice_residual(world,final['targets'],mu) if max(world.w)-min(world.w)<1e-12 else None
    ideal=idealized(initial_world,rows[0]['mean_settings'],config.periods,k=config.k,beta=config.beta) if config.outside_kind=='none' else []
    summary=dict(initial_Y=rows[0]['mean_Y'],final_Y=final['mean_Y'],final_reward=final['reward'],final_target_Y=final['target_Y'],
        improvement=final['mean_Y']-rows[0]['mean_Y'],best_found_Y=final['best_found_Y'],gap_to_best_found=final['best_found_Y']-final['mean_Y'],global_certified=final['global_certified'],
        final_mean_settings=final['mean_settings'],final_targets=final['targets'],final_target_spending=final['target_spending'],
        nearest_stationary_index=final['nearest_stationary_index'],distance_to_stationary=final['distance_to_stationary'],
        within_one_percent_best=abs(final['mean_Y']-final['best_found_Y'])<=.01*max(abs(final['best_found_Y']),1e-12),
        settling_period=settling,cumulative_exploration_effect=sum(x['exploration_effect'] for x in rows),total_overload=sum(x['overload'] for x in rows),
        skipped_turns=sum(len(x['skipped']) for x in rows),jump_events=sum(len(x['jump_events']) for x in rows),
        bound_violations=sum(x['bound_violations'] for x in rows),target_path_length=total_steps,tail_target_range=float(np.max(np.ptp(tail,axis=0))),
        idealized_slice_residual=residual,actual_T=T,frequencies=list(freq),periods=config.periods,
        warning='Best-found gaps are not global gaps unless certified; period rewards may involve overload and targets need not be feasible')
    return dict(summary=summary,periods=rows,executions=execution_records,world_versions=versions,idealized_oracle_price_variant=ideal)
