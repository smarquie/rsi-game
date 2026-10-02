"""Version 0.5 process. Oracle diagnostics are isolated from private reviews."""
from dataclasses import replace
from itertools import combinations
from copy import deepcopy
import numpy as np
from .config import Config
from .function_state import FunctionState
from .fast import clear,best_responses,best_response
from .world import World,kappa
from .explore import frequencies,executions,schedule,amplitude,path
from .period import execute
from .review import review
from .deploy import deploy,bounds_for,price_flags,persistent_time
from .benchmarks import optimize
from .access import audit,local_geometry,accessibility
from .channels import transfer_path,estimate_transfer,transfer_update,full_fit
from .diagnostics import classify,decomposition
from .typology import descriptors

def commitment(s,world,i,config,p):
    half=config.w_min/2
    if config.commit=='motive' or config.remedy=='R4':
        G,C=s.belief[1:]; own=best_response(G,C,world.alpha[i],world.w[i],world.gamma[i],p,0,world.qbar)
        team=best_response(G,C,0,1,world.gamma[i],p/world.w[i],0,world.qbar)
        half=max(half,abs(own-team)+config.motive_margin)
    s.bounds=(max(0,s.target-half),min(world.qbar,s.target+half));s.mode='free'

def initial_state(world,config):
    states=[FunctionState(np.array((0.,config.g0,0.)),0.,(0.,world.qbar)) for _ in range(world.n)]
    q=deploy(world,states,config)['q']
    for i,s in enumerate(states):
        s.target=float(q[i]);s.skips=0
        if config.initial_targets is not None:s.target=float(config.initial_targets[i]);commitment(s,world,i,config,0)
    return dict(states=states,price=max(config.p_min,deploy(world,states,config)['price']),ema=None,previous_Y=float(world.Y(q)),clock=0)

def simulate(world,config=Config(),seed=0,checkpoint=None,benchmark=None,return_checkpoint=False):
    config.validate_world(world); n=world.n; state=deepcopy(checkpoint) if checkpoint else initial_state(world,config); states=state['states']
    rng=np.random.default_rng(np.random.SeedSequence([seed,505,1])); T=executions(n,config.T,'fullnr' if config.remedy=='R7' else config.frequencies)
    freq=frequencies(n,'fullnr' if config.remedy=='R7' else config.frequencies)
    bench=benchmark or optimize(world,config.multistarts,seed=int(world.hash[:8],16));V=bench['best']['Y']
    initial=deploy(world,states,config); base=initial['Y']; H=max(0,V-base); rows=[]; evaluation=0;resources=0.;exploration_resources=0.;access_records=[]
    learning=config.learning and config.remedy!='unreviewed'; pairs=config.channel_pairs or tuple(combinations(range(n),2))
    def append(r,dep,mean,spend,overload,flags,updates,extra):
        I=dep['Y']-base
        rows.append(dict(period=r,deployment_Y=dep['Y'],deployment_q=dep['q'],deployment_spending=dep['spending'],deployment_rationed=dep['rationed'],deployment_price=dep['price'],
            improvement=I,opportunity=max(0,V-dep['Y']),fraction=I/H if H>1e-9 else None,mean_Y=mean,mean_spending=spend,overload=overload,
            evaluations=evaluation,resources=resources,exploration_resources=exploration_resources,
            price=state['price'],price_flags=flags,targets=[s.target for s in states],beliefs=[s.belief.tolist() for s in states],bounds=[list(s.bounds) for s in states],
            skip_counts=[getattr(s,'skips',0) for s in states],updates=updates,**extra))
    append(0,initial,base,initial['spending'],0,initial['flags'],{},dict(kind='initial',pre_review_deployment_Y=base,exploration_cost=0.))
    for r in range(1,config.periods+1):
        if config.pin_targets is not None:
            for i,s in enumerate(states):s.bounds=(config.pin_targets[i],config.pin_targets[i]);s.mode='free'
        clock=state['clock']+r; dep=deploy(world,states,config); updates={}; extra={}; paths={}; centers=None
        kind='full' if learning and config.remedy=='R7' and clock%config.full_every==0 else 'channel' if learning and (config.remedy=='R6' or config.channel_pairs) and pairs and clock%config.channel_every==0 else 'local'
        beliefs=np.array([s.belief.copy() for s in states]); bounds=bounds_for(states,config,world.qbar)
        planned=schedule(clock,n,config.k,config.schedule,rng) if learning else []
        if kind=='channel':
            pair=pairs[(clock//config.channel_every-1)%len(pairs)]; q,u,a=transfer_path(world,dep['q'],pair,T,config.channel_amplitude);Y=world.Y(q);sp=world.spend(q)
            est=estimate_transfer(Y,u); new,step=transfer_update(world,dep['q'],pair,est,config.channel_eta,config.channel_break)
            for i in pair:states[i].target=float(new[i]);commitment(states[i],world,i,config,dep['price'])
            result=dict(q=q,Y=Y,spending=sp,price=dep['price'],overload=max(0,float(sp.mean()-world.B)))
            extra=dict(information='R6 public-signal fit; shared feasible-step clipping service for heterogeneous costs',channel_boundary_blocked=a<=1e-12,pair=list(pair),channel=est,channel_step=step,channel_amplitude=a,restricted_count=2)
        else:
            if kind=='full':planned=list(range(n))
            for i,s in enumerate(states):
                s.mode='free'
                if i in planned:
                    a=amplitude(s.belief[2],state['previous_Y'],s.scale,len(planned),config,world.qbar)
                    if a<=0:s.skips=getattr(s,'skips',0)+1;s.scale=min(1,2*s.scale)
                    else:
                        paths[i],s.center=path(s.target,a,freq[i],T,world.qbar);s.amplitude=a;s.bounds=(s.center-a,s.center+a);s.mode='exploring';s.skips=0
            bounds=np.array([s.bounds for s in states]); integral=config.price_rule=='integral' or config.remedy in ('R3','R1+R3')
            if integral:
                q=np.tile(best_responses(beliefs,world.alpha,world.w,world.gamma,state['price'],bounds),(T,1))
                for i,values in paths.items():q[:,i]=values
                result=dict(q=q,Y=world.Y(q),spending=world.spend(q),price=state['price'],overload=max(0,float(world.spend(q).mean()-world.B)))
            else:result=execute(world,beliefs,bounds,paths,T,config)
            flags=price_flags(world,beliefs,bounds,result['price'],paths,T,config.p_max)
            state['ema']=result['price'] if state['ema'] is None else config.lambda_p*state['ema']+(1-config.lambda_p)*result['price']
            used=state['ema'] if config.price_rule=='ema' or config.remedy=='R2' else result['price']
            center=np.mean(result['q'],axis=0)
            # Three truth-only reference clearing solves, excluded from effort.
            neutral=replace(world,alpha=(0.,)*n);mu0=clear(neutral,beliefs,bounds,paths,T,config.p_max).price
            bd=bounds_for(states,config,world.qbar);mu0d=clear(neutral,beliefs,bd,{},1,config.p_max).price
            truth=np.array([world.local_coeffs(i,dep['q']) for i in range(n)]);muc=clear(neutral,truth,bd,{},1,config.p_max).price
            for i in paths:
                s=states[i];old=s.target
                update=review(s,result['q'][:,i],result['Y'],used,world.gamma[i],world.w[i],config,world.qbar,state['previous_Y'],clock,prices=result.get('prices'))
                if update['updated']:
                    update['decomposition']=decomposition(*s.belief[1:],world.local_coeffs(i,center)[1],truth[i,1],world.C[i][i],used/world.w[i],mu0,mu0d,muc,world.gamma[i],world.qbar)
                    if config.remedy=='R5' and any(flags.values()):s.target=old;update['target_skipped_degenerate']=True
                    if config.remedy in ('R1','R1+R3'):s.target=float(old+np.clip(s.target-old,-config.step_cap*(n-1)*config.w_min/2,config.step_cap*(n-1)*config.w_min/2))
                    commitment(s,world,i,config,result['price'])
                updates[str(i)]=update
            if kind=='full' and len(paths)==n:
                fitted=full_fit(result['Y'],freq);amps=np.array([s.amplitude for s in states]);z=np.array([s.center for s in states]);C=np.array(fitted['C_dither'])/np.outer(amps,amps);g=np.array(fitted['gradient_dither'])/amps
                learned=replace(world,C=tuple(map(tuple,C)),b=tuple(g-2*C@z),Y0=float(fitted['Y_center']-g@z+z@C@z))
                move=accessibility(learned,dep['q'],n,.1,config.access_starts,seed)
                for i,s in enumerate(states):s.target=move['q'][i];commitment(s,world,i,config,result['price'])
                extra=dict(full_fit=fitted,joint_move=move,information='R7 fitted performance plus ORACLE cost/budget feasibility; not decentralized',restricted_count=n)
            if config.remedy=='oracle' and clock%config.full_every==0:
                move=accessibility(world,dep['q'],n,.1,config.access_starts,seed)
                for i,s in enumerate(states):s.target=move['q'][i];commitment(s,world,i,config,result['price'])
                extra=dict(joint_move=move,information='oracle true environment')
            state['price']=float(np.clip(max(result['price'],config.p_min)*np.exp(np.clip(config.eta_B*(result['spending'].mean()-world.B)/world.B,-50,50)),config.p_min,config.p_max)) if integral else result['price']
        flags=price_flags(world,beliefs,bounds,result['price'],paths,T,config.p_max)
        evaluation+=T;resources+=float(result['spending'].sum());state['previous_Y']=float(result['Y'].mean())
        for i in paths:exploration_resources+=float(world.gamma[i]*(kappa(paths[i]).sum()-T*kappa(states[i].center)))
        newdep=deploy(world,states,config)
        append(r,newdep,state['previous_Y'],float(result['spending'].mean()),result['overload'],flags,updates,dict(kind=kind,pre_review_deployment_Y=dep['Y'],exploration_cost=dep['Y']-state['previous_Y'],**extra))
        if r%config.access_every==0 or r==config.periods:access_records.append(dict(period=r,**audit(world,newdep['q'],config.access_starts)))
    final_access=access_records[-1] if access_records else audit(world,initial['q'],config.access_starts)
    I=[r['improvement'] for r in rows];phi=[r['fraction'] for r in rows];ta=persistent_time(I,config.absolute_target,config.persistence);tf=persistent_time(phi,config.fraction_target,config.persistence) if H>1e-9 else None
    summary=dict(initial_Y=base,final_Y=rows[-1]['deployment_Y'],improvement=I[-1],headroom=H,fraction=phi[-1],opportunity=rows[-1]['opportunity'],best_found_Y=V,global_certified=bench['global_certified'],
        failure_class=classify(rows,H,config,final_access),tau_absolute=ta,tau_fraction=tf,tau_absolute_evaluations=rows[ta]['evaluations'] if ta is not None else None,
        tau_fraction_evaluations=rows[tf]['evaluations'] if tf is not None else None,tau_absolute_resources=rows[ta]['resources'] if ta is not None else None,
        evaluations=evaluation,resources=resources,actual_T=T,periods=config.periods,tail_std=float(np.std([r['deployment_Y'] for r in rows[-config.oscillation_window:]])),
        total_overload=float(sum(r['overload'] for r in rows)),deployment_rationing_periods=sum(r['deployment_rationed'] for r in rows),benchmark_warning='Noncertified opportunity is a lower bound; headroom fraction is an upper bound.',**local_geometry(world,rows[-1]['deployment_q']))
    answer=dict(summary=summary,periods=rows,accessibility=access_records,benchmark=bench,descriptors=descriptors(world),world=world.to_dict())
    if return_checkpoint:state['clock']+=config.periods;answer['checkpoint']=state
    return answer
