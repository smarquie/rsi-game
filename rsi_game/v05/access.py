"""Oracle accessibility searches. Positive witnesses are evidence; failed searches
are NOT impossibility proofs for nonconcave worlds."""
from itertools import combinations
import numpy as np
from scipy.optimize import minimize
from .benchmarks import kkt

def local_geometry(world,x):
    x=np.asarray(x); cp=np.array(world.gamma)/(1-x); v=world.grad(x)/cp
    plus=v[x<world.qbar-1e-9]; minus=v[x>1e-9]
    M=float(max(plus)-min(minus)) if len(plus) and len(minus) else None
    check=kkt(world,x); H=2*np.array(world.C)-check['multiplier']*np.diag(np.array(world.gamma)/(1-x)**2)
    curves=[]
    for i,j in combinations(range(world.n),2):
        if min(x[i],x[j])>1e-9 and max(x[i],x[j])<world.qbar-1e-9:
            d=np.zeros(world.n); d[i]=1/cp[i]; d[j]=-1/cp[j];curves.append(float(d@H@d))
    return dict(misallocation=M,kkt_residual=check['residual'],multiplier=check['multiplier'],max_transfer_curvature=max(curves,default=None),binding=abs(float(world.spend(x))-world.B)<1e-7)

def accessibility(world,x,m,rho,starts=20,seed=0):
    x=np.asarray(x,dtype=float); best=x.copy(); value=float(world.Y(x)); rng=np.random.default_rng(seed); attempts=0; failures=0
    # All supports of exactly m contain every smaller support because zero moves
    # are admissible within each support.
    for support in combinations(range(world.n),min(m,world.n)):
        idx=np.array(support); lo=np.maximum(0,x[idx]-rho); hi=np.minimum(world.qbar,x[idx]+rho)
        def expand(z): q=x.copy();q[idx]=z;return q
        for j in range(starts):
            start=x[idx] if j==0 else rng.uniform(lo,hi)
            result=minimize(lambda z:-float(world.Y(expand(z))),start,jac=lambda z:-world.grad(expand(z))[idx],bounds=list(zip(lo,hi)),
                constraints=[dict(type='ineq',fun=lambda z:world.B-world.spend(expand(z)),jac=lambda z:-np.array(world.gamma)[idx]/(1-z))],method='SLSQP',options=dict(ftol=1e-11,maxiter=300))
            attempts+=1; failures+=not result.success; q=expand(result.x)
            if world.spend(q)<=world.B+1e-8 and world.Y(q)>value:best=q;value=float(world.Y(q))
    return dict(m=m,rho=rho,gain=max(0.,value-float(world.Y(x))),q=best.tolist(),attempts=attempts,optimizer_failures=failures,certificate='feasible_lower_bound')

def audit(world,x,starts=20,radii=(.05,.1,.2)):
    geometry=local_geometry(world,x); searches=[accessibility(world,x,m,r,starts,505) for r in radii for m in sorted(set((1,2,min(3,world.n),world.n))) if m<=world.n]
    return dict(**geometry,searches=searches,coordination_witnesses={str(r):next((s['m'] for s in searches if s['rho']==r and s['gain']>1e-7),None) for r in radii},warning='No positive witness does not certify a barrier or impossibility.')


def barrier_search(world,x,m,starts=40,tolerance=1e-7):
    """Numerical crossing bracket; NOT a certified lower radius bound."""
    lo=0.;hi=world.qbar;top=accessibility(world,x,m,hi,starts)
    if top['gain']<=tolerance:return dict(radius=None,status='no_positive_witness')
    for _ in range(18):
        mid=(lo+hi)/2;result=accessibility(world,x,m,mid,starts)
        if result['gain']>tolerance:hi=mid
        else:lo=mid
    return dict(radius=hi,search_bracket=[lo,hi],status='numerical_estimate_not_certificate',gain_tolerance=tolerance)
