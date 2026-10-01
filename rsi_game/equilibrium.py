"""Best-response search with certified regrets; exhaustive finite-grid analysis."""
from dataclasses import dataclass
from functools import lru_cache
from collections import Counter, deque
import numpy as np
from .params import TechParams
from .grids import SHAPE, LOW, HIGH, CANONICAL
from .episode import evaluate

@dataclass(frozen=True)
class Solution:
    profile: tuple
    converged: bool
    regret: float
    sweeps: int
    method: str


def deviations(profile, role):
    x=np.tile(profile,(SHAPE[role],1)); x[:,role]=np.arange(SHAPE[role]); return x


def regrets(profile,cfg,tech):
    u=evaluate(profile,cfg,tech).utilities[0]
    return np.array([max(0.,float(evaluate(deviations(profile,i),cfg,tech).utilities[:,i].max()-u[i])) for i in range(5)])


def feasible_start(start,cfg,tech):
    a=tuple(map(int,start))
    if evaluate(a,cfg,tech).feasible[0]: return a
    if not evaluate(LOW,cfg,tech).feasible[0]: raise ValueError('Configuration overhead alone exceeds the budget')
    return LOW


@lru_cache(maxsize=1024)
def solve(cfg,tech=TechParams(),start=CANONICAL,tolerance=1e-9,max_sweeps=50,logit_steps=2000,temperature=.01):
    a=feasible_start(start,cfg,tech)
    for sweep in range(1,max_sweeps+1):
        changed=False
        for i in range(5):
            options=deviations(a,i); u=evaluate(options,cfg,tech).utilities[:,i]
            j=int(np.argmax(u))
            if u[j]>u[a[i]]+tolerance: a=tuple(map(int,options[j])); changed=True
        if not changed:
            regret=float(regrets(a,cfg,tech).max())
            return Solution(a,regret<=tolerance,regret,sweep,'best_response')
    # Fixed, configuration-specific seed: cache/order independent fallback.
    rng=np.random.default_rng(int(cfg.fingerprint,16)); seen=[]
    for t in range(logit_steps):
        i=int(rng.integers(5)); options=deviations(a,i); u=evaluate(options,cfg,tech).utilities[:,i]
        p=np.exp((u-u.max())/temperature); p/=p.sum()
        a=tuple(map(int,options[rng.choice(len(p),p=p)]))
        if t>=logit_steps//2: seen.append(a)
    a=Counter(seen).most_common(1)[0][0]
    return Solution(a,False,float(regrets(a,cfg,tech).max()),max_sweeps,'logit_modal_non_equilibrium')


def team_search(cfg,tech=TechParams(),current=CANONICAL):
    best=None
    for start in dict.fromkeys((LOW,HIGH,CANONICAL,current)):
        a=feasible_start(start,cfg,tech)
        for _ in range(100):
            changed=False
            for i in range(5):
                options=deviations(a,i); w=evaluate(options,cfg,tech).welfare; j=int(w.argmax())
                if w[j]>w[a[i]]+1e-12: a=tuple(map(int,options[j])); changed=True
            if not changed: break
        value=float(evaluate(a,cfg,tech).welfare[0])
        if best is None or value>best['welfare']: best=dict(profile=a,welfare=value,exact=False)
    return best


def diagnostics(cfg,tech,current):
    solutions=[solve(cfg,tech,s) for s in dict.fromkeys((LOW,HIGH,CANONICAL,current))]
    equilibria={s.profile for s in solutions if s.converged}
    return dict(equilibria=[list(a) for a in sorted(equilibria)],multiple_found=len(equilibria)>1,
                all_starts_converged=all(s.converged for s in solutions),
                caveat='Multiple starts cannot establish uniqueness')


def exhaustive(cfg,tech=TechParams(),attractors=False,chunk_size=20000):
    """Enumerate all profiles, all pure feasible equilibria and global team optimum.

    Optional attractors: entire deterministic Gauss-Seidel sweep map with incumbent
    tie retention. This is exhaustive for this map only, not all update schedules.
    """
    n=int(np.prod(SHAPE)); U=np.empty((n,5)); W=np.empty(n); feasible=np.empty(n,dtype=bool)
    for offset in range(0,n,chunk_size):
        ids=np.arange(offset,min(n,offset+chunk_size)); profiles=np.column_stack(np.unravel_index(ids,SHAPE))
        ev=evaluate(profiles,cfg,tech); U[ids]=ev.utilities; W[ids]=ev.welfare; feasible[ids]=ev.feasible
    if not feasible.any(): raise ValueError('No feasible profiles')
    eq=feasible.copy(); strides=np.array([int(np.prod(SHAPE[i+1:])) for i in range(5)])
    maps=[]
    for i in range(5):
        cube=U[:,i].reshape(SHAPE); mx=np.max(cube,axis=i,keepdims=True)
        eq &= (cube>=mx-1e-9).ravel()
        if attractors:
            chosen=np.argmax(cube,axis=i); chosen=np.expand_dims(chosen,axis=i)
            axis=np.arange(SHAPE[i]).reshape(tuple(SHAPE[i] if j==i else 1 for j in range(5)))
            selected=np.where(cube>=mx-1e-9,axis,chosen)
            ids=np.arange(n); old=(ids//strides[i])%SHAPE[i]
            maps.append(ids+(selected.ravel()-old)*strides[i])
    ids=np.flatnonzero(eq); best=int(np.argmax(W))
    result=dict(profiles=n,feasible_profiles=int(feasible.sum()),pure_equilibria=[dict(profile=list(map(int,np.unravel_index(int(j),SHAPE))),welfare=float(W[j])) for j in ids],
                team_optimum=dict(profile=list(map(int,np.unravel_index(best,SHAPE))),welfare=float(W[best]),exact=True),
                pure_price_of_anarchy=float(W[best]-W[ids].min()) if len(ids) else None)
    if attractors:
        nxt=np.arange(n)
        for m in maps: nxt=m[nxt]
        # Exclude infeasible initial states; every feasible best response stays feasible.
        valid=np.flatnonzero(feasible); degree=np.bincount(nxt[valid],minlength=n)
        queue=deque(map(int,valid[degree[valid]==0])); peeled=[]
        while queue:
            v=queue.popleft(); peeled.append(v); w=int(nxt[v]); degree[w]-=1
            if degree[w]==0: queue.append(w)
        label=np.full(n,-1,dtype=int); cycles=[]
        for v in valid[degree[valid]>0]:
            if label[v]>=0: continue
            cycle=[]; w=int(v); k=len(cycles)
            while label[w]<0: label[w]=k; cycle.append(w); w=int(nxt[w])
            cycles.append(cycle)
        for v in reversed(peeled): label[v]=label[nxt[v]]
        sizes=np.bincount(label[valid],minlength=len(cycles))
        result['sweep_attractors']=[dict(period=len(c),basin_profiles=int(sizes[k]),
            profiles=[list(map(int,np.unravel_index(j,SHAPE))) for j in c]) for k,c in enumerate(cycles)]
        result['dynamics_scope']='All feasible starts; fixed I,M,R,G,C sweep; current-action ties; tolerance 1e-9'
    return result
