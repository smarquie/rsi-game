"""Paired world-level randomization and Holm familywise correction."""
from itertools import product
import numpy as np

def paired_sign_test(values,seed=505):
    a=np.asarray(values,dtype=float)
    if len(a)<2:return None
    observed=abs(a.mean());rng=np.random.default_rng(seed)
    if len(a)<=16:
        stats=[abs(np.dot(s,a)/len(a)) for s in product((-1,1),repeat=len(a))]
        return float(np.mean(np.array(stats)>=observed-1e-14))
    exceed=0;N=10000
    for _ in range(100):exceed+=np.count_nonzero(abs((rng.choice((-1,1),(100,len(a)))*a).mean(axis=1))>=observed-1e-14)
    return (exceed+1)/(N+1)

def holm(rows,pkey='p_value',family='family'):
    groups={r.get(family,'all') for r in rows}
    for group in groups:
        subset=sorted((r for r in rows if r.get(family,'all')==group and r.get(pkey) is not None),key=lambda r:r[pkey]);prior=0.
        for i,r in enumerate(subset):prior=max(prior,min(1.,(len(subset)-i)*r[pkey]));r['p_holm']=prior
    return rows
