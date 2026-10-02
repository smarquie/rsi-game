"""Architectural schedule and frequencies. No state-dependent coordination."""
from functools import lru_cache
import numpy as np


def nonresonant(freq):
    m=tuple(freq)
    if len(set(m))!=len(m) or any(x<=0 or int(x)!=x for x in m): return False
    for i,mi in enumerate(m):
        for j,mj in enumerate(m):
            if j==i: continue
            if mj in (2*mi,3*mi) or 2*mj==mi: return False
            for k,mk in enumerate(m):
                if k==j: continue
                if mj+mk in (mi,2*mi) or abs(mj-mk) in (mi,2*mi): return False
    return True


@lru_cache(maxsize=32)
def frequencies(n,kind='nonresonant'):
    if kind=='resonant': return tuple(range(1,n+1))
    # Every admissible finite prefix extends at a sufficiently high frequency;
    # choosing the smallest admissible next value gives the lexicographic set.
    result=[]; candidate=1
    while len(result)<n:
        if (fully_nonresonant if kind=='fullnr' else nonresonant)(result+[candidate]): result.append(candidate)
        candidate+=1
        if candidate>100000: raise ValueError('Frequency search exceeded safety limit')
    return tuple(result)


def executions(n,requested,kind='nonresonant'):
    return max(requested,6*max(frequencies(n,kind))+2)


def schedule(period,n,k,kind,rng):
    if period==0: return []
    if kind=='all': return list(range(n))
    if kind=='random': return sorted(map(int,rng.choice(n,k,replace=False)))
    return [((period-1)*k+j)%n for j in range(k)]


def amplitude(curvature,previous_Y,scale,k,config,qbar):
    permitted=np.sqrt(2*config.eps_dis*max(abs(previous_Y),config.Y_scale)/(k*max(-curvature,config.curvature_floor)))
    a=min(config.a_max,scale*permitted,qbar/2)
    return float(a) if a>=config.w_min/2 and a>1e-14 else 0.


def path(target,a,m,T,qbar):
    z=float(np.clip(target,a,qbar-a))
    return z+a*np.sin(2*np.pi*m*np.arange(1,T+1)/T),z


def fully_nonresonant(freq):
    from itertools import combinations
    signature=list(freq)+[2*m for m in freq]
    for a,b in combinations(freq,2): signature.extend((abs(a-b),a+b))
    return min(signature,default=0)>0 and len(signature)==len(set(signature))
