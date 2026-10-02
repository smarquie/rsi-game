"""Standardized feasible deployment (Definition 5.3); no learning here."""
import numpy as np
from .fast import clear,best_responses
from .world import kappa

def bounds_for(states,config,qbar):
    return np.array([(max(0,s.target-config.w_min/2),min(qbar,s.target+config.w_min/2)) if s.mode=='exploring' else s.bounds for s in states])

def price_flags(world,beliefs,bounds,price,paths=None,T=1,p_max=1000.):
    paths=paths or {}; free=np.array([i for i in range(world.n) if i not in paths],dtype=int)
    def demand(p):
        return best_responses(np.asarray(beliefs)[free],np.array(world.alpha)[free],np.array(world.w)[free],np.array(world.gamma)[free],p,np.asarray(bounds)[free])
    zero=price<=1e-10; maximum=price>=p_max*(1-1e-9)
    current=demand(price)
    explorer_cost=sum(world.gamma[i]*float(np.mean(kappa(v))) for i,v in paths.items())
    clearing=abs(explorer_cost+float(kappa(current)@np.array(world.gamma)[free])-world.B)<1e-7
    # Smallest-price selection lies on the LEFT edge of a clearing plateau.
    # Comparing both sides only would miss the one-sided flat interval.
    flat=bool(not zero and not maximum and clearing and (np.max(abs(demand(price*(1+1e-5))-current),initial=0)<1e-10 or np.max(abs(demand(price*(1-1e-5))-current),initial=0)<1e-10))
    return dict(zero=zero,maximum=maximum,setvalued=flat)

def deploy(world,states,config):
    beliefs=np.array([s.belief for s in states]); bounds=bounds_for(states,config,world.qbar)
    fast=clear(world,beliefs,bounds,{},1,config.p_max,config.price_tol)
    q=fast.q[0].copy(); spending=float(world.spend(q)); rationed=spending>world.B+1e-8
    if rationed: q=-np.expm1(-kappa(q)*world.B/spending)
    return dict(q=q.tolist(),Y=float(world.Y(q)),spending=float(world.spend(q)),price=fast.price,rationed=rationed,
        flags=price_flags(world,beliefs,bounds,fast.price,p_max=config.p_max),status=fast.status)

def persistent_time(values,threshold,L):
    return next((i for i in range(len(values)-L+1) if min(values[i:i+L])>=threshold),None)
