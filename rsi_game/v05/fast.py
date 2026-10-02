"""Exact one-dimensional optimization and average-budget competitive clearing."""
from dataclasses import dataclass
import numpy as np
from .world import kappa


def candidates(G,C,alpha,w,gamma,p,lo,hi):
    beta1=w*G+alpha; beta2=2*w*C
    roots=[]
    if abs(beta2)<1e-12:
        if beta1>0: roots=[1-p*gamma/beta1]
    else:
        # Use the stable quadratic formula (avoids cancellation near zero roots).
        b=beta1-beta2; c=p*gamma-beta1; discriminant=b*b-4*beta2*c
        if discriminant>=0:
            root=np.sqrt(discriminant); t=-.5*(b+np.copysign(root,b))
            roots=[t/beta2]
            if abs(t)>1e-300: roots.append(c/t)
    q=np.array(sorted(set([float(lo),float(hi)]+[float(x) for x in roots if lo<x<hi])))
    utility=beta1*q+w*C*q*q-p*gamma*kappa(q)
    return q,utility


def best_response(G,C,alpha,w,gamma,p,lo,hi):
    q,u=candidates(G,C,alpha,w,gamma,p,lo,hi)
    # Only numerical ties, not a large absolute utility tolerance at tiny scales.
    threshold=8*np.finfo(float).eps*max(1.,float(np.max(abs(u))))
    return float(q[np.flatnonzero(u>=u.max()-threshold)[0]])


def best_responses(beliefs,alpha,w,gamma,p,bounds):
    if len(beliefs)==0: return np.empty(0)
    # Concave/linear beliefs dominate the baseline; solve derivatives by vector
    # arithmetic without a scalar polynomial solver per role and price iteration.
    G=beliefs[:,1]; C=beliefs[:,2]; a=np.asarray(alpha); w=np.asarray(w); gamma=np.asarray(gamma)
    lo=bounds[:,0]; hi=bounds[:,1]
    if np.any(C>0):
        return np.array([best_response(g,c,ai,wi,gi,p,l,h) for g,c,ai,wi,gi,(l,h) in zip(G,C,a,w,gamma,bounds)])
    b1=w*G+a; b2=2*w*C
    d_lo=b1+b2*lo-p*gamma/(1-lo); d_hi=b1+b2*hi-p*gamma/(1-hi)
    out=lo.copy(); upper=d_hi>0; out[upper]=hi[upper]
    inside=(d_lo>0)&~upper
    linear=inside&(abs(b2)<1e-12)
    out[linear]=1-p*gamma[linear]/b1[linear]
    nonlinear=inside&~linear
    bb=b1[nonlinear]-b2[nonlinear]; cc=p*gamma[nonlinear]-b1[nonlinear]; aa=b2[nonlinear]
    root=np.sqrt(np.maximum(0,bb*bb-4*aa*cc)); tmp=-.5*(bb+np.copysign(root,bb))
    r1=tmp/aa; r2=np.divide(cc,tmp,out=np.zeros_like(cc),where=abs(tmp)>1e-300)
    l=lo[nonlinear]; h=hi[nonlinear]; out[nonlinear]=np.where((r1>=l)&(r1<=h),r1,r2)
    return np.clip(out,lo,hi)


@dataclass
class FastResult:
    price: float
    q: np.ndarray  # T × n realized settings
    theoretical_spending: float
    realized_spending: float
    status: str
    jump_events: list
    bound_violations: int
    complementarity: float


def clear(world,beliefs,bounds,paths,T,p_max=1000.,tolerance=1e-10,budget_rule='price'):
    n=world.n; free=np.array([i for i in range(n) if i not in paths],dtype=int)
    gamma=np.array(world.gamma); beliefs=np.asarray(beliefs); bounds=np.asarray(bounds)
    q=np.zeros((T,n))
    for i,values in paths.items(): q[:,i]=values
    explorer_cost=float(sum(gamma[i]*np.mean(kappa(values)) for i,values in paths.items()))
    def demands(p):
        return best_responses(beliefs[free],np.array(world.alpha)[free],np.array(world.w)[free],gamma[free],p,bounds[free])
    def spend(x): return explorer_cost+float(kappa(x)@gamma[free])
    at_zero=demands(0.); events=[]
    if budget_rule=='ration':
        total=spend(at_zero); cost=total-explorer_cost
        scale=max(0.,min(1.,(world.B-explorer_cost)/cost)) if cost>0 else 1.
        q[:,free]=-np.expm1(-scale*kappa(at_zero))
        realized=float(np.mean(world.spend(q))); violations=int(np.count_nonzero(q[:,free]<bounds[free,0]-1e-10))
        return FastResult(0.,q,realized,realized,'rationed' if scale<1 else 'slack',[],violations,0.)
    if spend(at_zero)<=world.B+tolerance:
        q[:,free]=at_zero; total=spend(at_zero)
        return FastResult(0.,q,total,total,'slack',[],0,0.)
    cap=demands(p_max)
    if spend(cap)>world.B+tolerance:
        q[:,free]=cap; total=spend(cap)
        return FastResult(p_max,q,total,total,'price_cap_or_infeasible',[],0,p_max*abs(total-world.B))
    low=0.; high=p_max; q_low=at_zero; q_high=cap
    for _ in range(100):
        mid=(low+high)/2; proposed=demands(mid)
        if spend(proposed)>world.B: low=mid; q_low=proposed
        else: high=mid; q_high=proposed
        if high-low<tolerance: break
    p=high; q[:,free]=q_high; theory=spend(q_high)
    if spend(q_low)-theory>1e-6 and world.B-theory>1e-8:
        # Multiple simultaneous switches may be needed; the draft's 'one' switch
        # is not always enough. Relaxed mixture is exact; finite T rounds down.
        needed=world.B-theory
        for j,i in enumerate(free):
            if q_low[j]-q_high[j]<1e-7: continue
            lowq=float(q_high[j]); highq=float(q_low[j])
            qs,us=candidates(*beliefs[i,1:],world.alpha[i],world.w[i],world.gamma[i],p,*bounds[i])
            def util(x): return (world.w[i]*beliefs[i,1]+world.alpha[i])*x+world.w[i]*beliefs[i,2]*x*x-p*world.gamma[i]*kappa(x)
            regret=max(float(us.max()-util(lowq)),float(us.max()-util(highq)))
            if regret>1e-6: continue
            increment=world.gamma[i]*float(kappa(highq)-kappa(lowq))
            fraction=min(1.,max(0.,needed/increment)); count=int(np.floor(T*fraction+1e-10))
            if count:
                # Evenly spread switches; deterministic, never fed to reviews.
                indices=np.floor((np.arange(count)+.5)*T/count).astype(int); q[indices,i]=highq
            theory+=fraction*increment; needed-=fraction*increment
            events.append(dict(role=int(i),low=lowq,high=highq,theoretical_high_share=float(fraction),realized_high_share=count/T,utility_regret=regret))
            if needed<=1e-10: break
    realized=float(np.mean(world.spend(q)))
    status='finite_horizon_mixture' if events else 'cleared'
    return FastResult(float(p),q,float(theory),realized,status,events,0,float(p*abs(realized-world.B)))
