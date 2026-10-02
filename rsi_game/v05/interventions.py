"""Paired 2x2 interventions: one shared checkpoint and matched random streams."""
from dataclasses import replace
from copy import deepcopy
import numpy as np
from .world import World
from .deploy import deploy
from .simulation import simulate,commitment
from .function_state import FunctionState
from .benchmarks import optimize

def edit(world,kind,q,scale=.3,role=0,pair=None,seed=0):
    b=np.array(world.b);c=np.array(world.C);g=np.array(world.gamma);q=np.asarray(q);Y0=world.Y0
    if kind=='capability':b[role]+=scale
    elif kind=='cost':g[role]*=1-scale
    elif kind in ('interference','complementarity'):
        candidates=[(i,j) for i in range(world.n) for j in range(i+1,world.n) if (c[i,j]<0 if kind=='interference' else c[i,j]>=0)]
        if pair is None:pair=candidates[0] if candidates else None
        if pair is None:return world,dict(kind=kind,eligible=False)
        i,j=pair;c[i,j]=c[j,i]=c[i,j]*(1-scale) if kind=='interference' else c[i,j]+scale
    elif kind=='invisible':
        rng=np.random.default_rng(np.random.SeedSequence([seed,505,2]));D=np.triu(rng.uniform(0,scale,c.shape),1);D+=D.T
        c+=D;b-=2*D@q;Y0+=float(q@D@q)
    elif kind in ('newfunction_active','newfunction_inactive'):
        n=world.n;C=np.zeros((n+1,n+1));C[:n,:n]=c;C[n,n]=-.2
        if kind=='newfunction_active':C[n,:n]=C[:n,n]=scale
        return World(tuple(b)+(scale if kind=='newfunction_active' else .01,),tuple(map(tuple,C)),tuple(g)+(1.,),world.B,world.alpha+(0.,),world.w+(1.,),Y0,world.qbar),dict(kind=kind,eligible=True)
    elif kind in ('coordinator','process'):return world,dict(kind=kind,eligible=True)
    else:raise ValueError(kind)
    return replace(world,b=tuple(b),C=tuple(map(tuple,c)),gamma=tuple(g),Y0=Y0),dict(kind=kind,eligible=True)

def paired(world,config,kind,seed=0,pre=150,post=150,scale=.3,pin=False):
    before=simulate(world,replace(config,periods=pre),seed,return_checkpoint=True);snapshot=before.pop('checkpoint');q=deploy(world,snapshot['states'],config)['q']
    edited,event=edit(world,kind,q,scale,seed=seed);arms={}
    benchmarks=[before['benchmark'],optimize(edited,config.multistarts,seed)]
    for changed in (0,1):
        w=edited if changed else world;cfg=replace(config,pin_targets=tuple(q)) if pin else config
        if changed and kind=='coordinator':cfg=replace(cfg,remedy='R6')
        if changed and kind=='process':cfg=replace(cfg,remedy='R3')
        for learning in (0,1):
            state=deepcopy(snapshot)
            if w.n>world.n:
                s=FunctionState(np.array((0.,cfg.g0,0.)),0.,(0.,w.qbar));s.skips=0;state['states'].append(s)
            if pin:
                for i,s in enumerate(state['states']):s.bounds=(q[i],q[i]);s.target=q[i]
            arms[f'{changed}{learning}']=simulate(w,replace(cfg,periods=post,learning=bool(learning)),seed,checkpoint=state,benchmark=benchmarks[changed])
    # D: evaluate unchanged allocation (new coordinate zero); paired Gamma uses
    # each arm's deployed last-L mean. Changed no-learning arm includes clearing.
    L=min(config.persistence,post+1)
    ends={k:float(np.mean([r['deployment_Y'] for r in v['periods'][-L:]])) for k,v in arms.items()}
    qnew=q+[0.] if edited.n>world.n else q
    return dict(kind='paired',event=event,pin=pin,pre=before,arms=arms,
        effects=dict(active_function_before=bool(q[0]>1e-8),new_function_final_active=bool(arms['11']['periods'][-1]['deployment_q'][-1]>1e-8) if edited.n>world.n else None,D=float(edited.Y(qnew)-world.Y(q)),F=benchmarks[1]['best']['Y']-benchmarks[0]['best']['Y'],Gamma0=ends['10']-ends['00'],Gamma1=ends['11']-ends['01'],A=(ends['11']-ends['01'])-(ends['10']-ends['00']),headroom=before['summary']['headroom']),
        warning='F uses best-found ceilings unless both certified; pinned invisible control is exact only while non-explorers remain fixed.')
