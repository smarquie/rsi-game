"""Bounded catalogue selection with explicit trial cost and state rollback."""
from copy import deepcopy
from dataclasses import replace
import numpy as np
from .simulation import simulate
from .interventions import edit
from .deploy import deploy

CATALOGUE=('U1','U2','U3','U4','U5','U6')
def apply(world,config,code,q):
    if code=='U1':return (edit(world,'interference',q,.5,pair=(0,1))[0] if world.n>1 and world.C[0][1]<0 else world),config
    if code=='U2':return edit(world,'cost',q,.3)[0],config
    if code=='U3':return world,replace(config,channel_pairs=((0,1),))
    if code=='U4':return world,replace(config,price_rule='integral',eta_B=.1)
    if code=='U5':return world,replace(config,beta=.3,commit='motive')
    if code=='U6':return world,replace(config,remedy='R7')
    raise ValueError(code)

def select(world,config,seed=0,episodes=6,trial_periods=40,cost_fraction=.01,policy='cycle'):
    if policy not in ('cycle','eps_greedy'):raise ValueError(policy)
    rng=np.random.default_rng(np.random.SeedSequence([seed,505,3]));warm=simulate(world,replace(config,periods=40),seed,return_checkpoint=True);state=warm.pop('checkpoint')
    H=warm['summary']['headroom'];accepted=[];logs=[];evaluations=warm['summary']['evaluations'];resources=warm['summary']['resources'];gains={u:[] for u in CATALOGUE};reference=warm
    for e in range(episodes):
        # Proposal sees catalogue labels and past measured gains only.
        code=CATALOGUE[e%6] if policy=='cycle' or e<6 or rng.random()<.1 else max(CATALOGUE,key=lambda u:np.mean(gains[u]) if gains[u] else -np.inf)
        snapshot=deepcopy(state);oldworld=world;oldconfig=config;q=deploy(world,state['states'],config)['q'];candidate,cfg=apply(world,config,code,q)
        trialworld=replace(candidate,B=candidate.B*(1-cost_fraction));trial=simulate(trialworld,replace(cfg,periods=trial_periods),seed+e+1,checkpoint=state,return_checkpoint=True)
        L=min(config.persistence,trial_periods+1);prior=float(np.mean([r['deployment_Y'] for r in reference['periods'][-L:]]));score=float(np.mean([r['deployment_Y'] for r in trial['periods'][-L:]]));gain=score-prior;accept=gain>.005*H
        evaluations+=trial['summary']['evaluations'];resources+=trial['summary']['resources']+trial_periods*trial['summary']['actual_T']*candidate.B*cost_fraction;gains[code].append(gain)
        trialstate=trial.pop('checkpoint')
        if accept:
            world=candidate;config=cfg;state=trialstate;accepted.append(code)
            # Evaluate the restored budget before the next comparison. Costs and
            # these executions remain charged, irrespective of later rollback.
            reference=simulate(world,replace(config,periods=config.persistence),seed+1000+e,checkpoint=state,return_checkpoint=True);state=reference.pop('checkpoint');evaluations+=reference['summary']['evaluations'];resources+=reference['summary']['resources']
        else:state=snapshot;world=oldworld;config=oldconfig
        logs.append(dict(episode=e,edit=code,accepted=accept,gain=gain,threshold=.005*H,trial=trial,implementation_cost_per_execution=candidate.B*cost_fraction,cumulative_evaluations=evaluations,cumulative_resources=resources))
    return dict(kind='structural',accepted=accepted,transferable_process_edits=[u for u in accepted if u in ('U3','U4','U5','U6')],episodes=logs,evaluations=evaluations,resources=resources,
        warning='Catalogue-limited adaptation, not open-ended recursive improvement. U6 uses oracle feasibility. Transfer must be evaluated on fresh worlds.')
