"""Truth-only benchmarks, KKT diagnostics and optional bounded global certification.

Multi-start SLSQP finds candidate optima; it never certifies a nonconcave global
optimum. The branch-and-bound routine returns an explicit upper/lower gap.
"""
from dataclasses import replace
from itertools import product
import heapq
import numpy as np
from scipy.optimize import minimize, nnls
from scipy.linalg import null_space
from .world import World, kappa
from .fast import clear, best_response


def feasible_scale(world,q):
    q=np.clip(q,0,world.qbar); spending=float(world.spend(q))
    return -np.expm1(-kappa(q)*min(1.,world.B/max(spending,1e-300)))


def kkt(world,q,tol=2e-6):
    q=np.asarray(q); g=world.grad(q); cost_gradient=np.array(world.gamma)/(1-q)
    active=[]; labels=[]
    if world.B-world.spend(q)<tol:
        active.append(cost_gradient); labels.append('budget')
    for i in range(world.n):
        if q[i]<tol: active.append(-np.eye(world.n)[i]); labels.append(f'lower_{i}')
        if world.qbar-q[i]<tol: active.append(np.eye(world.n)[i]); labels.append(f'upper_{i}')
    if active:
        matrix=np.array(active).T; multipliers,residual=nnls(matrix,g); residual=float(np.max(abs(g-matrix@multipliers)))
        mu=float(multipliers[labels.index('budget')]) if 'budget' in labels else 0.
        # Equality tangent only. Weakly active inequalities need a critical-cone
        # check, so this diagnostic is not a second-order sufficiency certificate.
        tangent=null_space(matrix.T)
    else: residual=float(np.max(abs(g))); mu=0.; tangent=np.eye(world.n)
    H=2*np.array(world.C)-mu*np.diag(np.array(world.gamma)/(1-q)**2)
    eigenvalues=np.linalg.eigvalsh(tangent.T@H@tangent).tolist() if tangent.shape[1] else []
    return dict(residual=residual,multiplier=mu,feasibility=max(0.,float(world.spend(q)-world.B)),
                complementarity=float(mu*abs(world.spend(q)-world.B)),tangent_eigenvalues=eigenvalues,
                tangent_warning='Equality-tangent diagnostic; weakly active critical cone is not certified')


def optimize(world,starts=300,seed=0):
    rng=np.random.default_rng(seed); initial=[np.zeros(world.n),feasible_scale(world,np.full(world.n,.6))]
    if world.n<=8:
        initial.extend(feasible_scale(world,np.array(v)*.95) for v in product((0,1),repeat=world.n))
    initial=initial[:starts]
    initial.extend(feasible_scale(world,rng.uniform(0,.95,world.n)) for _ in range(max(0,starts-len(initial))))
    solutions=[]; failed=0
    for start in initial:
        result=minimize(lambda q:-float(world.Y(q)),start,jac=lambda q:-world.grad(q),bounds=[(0,world.qbar)]*world.n,
            constraints=[dict(type='ineq',fun=lambda q:world.B-world.spend(q),jac=lambda q:-np.array(world.gamma)/(1-q))],
            method='SLSQP',options=dict(ftol=1e-12,maxiter=1000))
        q=feasible_scale(world,result.x); check=kkt(world,q)
        if check['residual']>1e-6 or check['feasibility']>1e-8: failed+=1
        item=dict(q=q.tolist(),Y=float(world.Y(q)),spending=float(world.spend(q)),optimizer_success=bool(result.success),**check)
        if not any(np.max(abs(q-np.array(s['q'])))<1e-4 for s in solutions): solutions.append(item)
    solutions.sort(key=lambda s:s['Y'],reverse=True)
    eigen=np.linalg.eigvalsh(world.C)
    valid=[s for s in solutions if s['residual']<1e-6 and s['feasibility']<1e-8]
    best=solutions[0]
    return dict(best=best,solutions=solutions,validated_stationary_points=valid,starts=len(initial),failed_kkt_starts=failed,
                eigenvalues=eigen.tolist(),global_certified=bool(eigen[-1]<=1e-12 and best['residual']<1e-6),
                status='concave_KKT_global' if eigen[-1]<=1e-12 and best['residual']<1e-6 else 'best_found_not_global_certificate')


def informed_equilibrium(world,max_iterations=10000,damping=.3):
    bounds=np.tile((0.,world.qbar),(world.n,1)); q=feasible_scale(world,np.full(world.n,.5)); converged=False
    for it in range(max_iterations):
        beliefs=np.array([world.local_coeffs(i,q) for i in range(world.n)])
        result=clear(world,beliefs,bounds,{},1)
        updated=(1-damping)*q+damping*result.q[0]
        if np.max(abs(updated-q))<1e-10: q=updated; converged=True; break
        q=updated
    return dict(q=q.tolist(),Y=float(world.Y(q)),price=result.price,iterations=it+1,converged=converged,
                residual=float(np.max(abs(result.q[0]-q))),spending=float(world.spend(q)))


def benchmark_bundle(world,starts=300):
    seed=int(world.hash[:8],16)
    team=optimize(world,starts,seed)
    diagonal=replace(world,C=tuple(map(tuple,np.diag(np.diag(world.C)))))
    ib=optimize(diagonal,min(starts,16),seed)['best']; ib={**ib,'Y_under_diagonal':ib['Y'],'Y':float(world.Y(ib['q']))}
    return dict(team=team,ignoring_interactions=ib,informed_free=informed_equilibrium(world))


def slice_residual(world,x,mu):
    x=np.asarray(x); targets=np.array([best_response(*world.local_coeffs(i,x)[1:],0.,1.,world.gamma[i],mu,0.,world.qbar) for i in range(world.n)])
    return dict(distance=float(np.max(abs(targets-x))),targets=targets.tolist(),budget_violation=max(0.,float(world.spend(x)-world.B)),
                complementarity=float(mu*abs(world.spend(x)-world.B)))


def idealized(world,start,periods=100,mu=None,k=1,beta=1.):
    """Fixed-multiplier coordinate ascent, or an explicit oracle-clearing variant.

    With exact commitments, clearing may not determine a unique price. The
    clearing variant explicitly computes an informed, unrestricted oracle price;
    it is labeled separately from the draft's implementable learning process.
    """
    q=np.asarray(start,dtype=float).copy(); trace=[]
    for r in range(periods):
        if mu is None:
            beliefs=np.array([world.local_coeffs(i,q) for i in range(world.n)])
            p=clear(world,beliefs,np.tile((0.,world.qbar),(world.n,1)),{},1).price
            mus=p/np.array(world.w)
        else: mus=np.full(world.n,mu)
        for i in [(r*k+j)%world.n for j in range(k)]:
            G,C=world.local_coeffs(i,q)[1:]
            target=best_response(G,C,0.,1.,world.gamma[i],mus[i],0.,world.qbar)
            q[i]+=beta*(target-q[i])
        trace.append(dict(q=q.tolist(),Y=float(world.Y(q)),spending=float(world.spend(q)),mu=mus.tolist()))
    return trace


def linear_support(world,g,lo,hi):
    """Dual upper bound on max g·q over this box and log-budget constraint."""
    gamma=np.array(world.gamma)
    def demands(mu):
        q=lo.copy(); positive=g>0
        q[positive]=np.clip(1-mu*gamma[positive]/g[positive],lo[positive],hi[positive]); return q
    q=demands(0.)
    if world.spend(q)<=world.B: return float(g@q)
    left=0.; right=max(1.,float(np.max(np.maximum(g,0)/gamma)))
    while world.spend(demands(right))>world.B and right<1e15: right*=2
    for _ in range(70):
        mid=(left+right)/2
        if world.spend(demands(mid))>world.B: left=mid
        else: right=mid
    mu=right; q=demands(mu)
    return float(g@q+mu*(world.B-world.spend(q)))


def certify_global(world,best_q=None,tolerance=1e-5,max_boxes=5000):
    """Spatial branch-and-bound with a concave quadratic upper envelope.

    Returned gap is a numerical certificate (floating-point, not interval
    arithmetic). A work limit returns an unresolved gap, never a false success.
    """
    if tolerance<=0 or max_boxes<1: raise ValueError('Positive tolerance/work limit required')
    x=feasible_scale(world,np.asarray(best_q if best_q is not None else np.zeros(world.n)))
    lower=float(world.Y(x)); queue=[]; counter=0; evaluated=0
    curvature=max(0.,float(np.linalg.eigvalsh(world.C)[-1]))
    def bound(lo,hi):
        nonlocal lower,x,evaluated
        if world.spend(lo)>world.B+1e-12: return None
        available=world.B-world.spend(lo)+np.array(world.gamma)*kappa(lo)
        hi=np.minimum(hi,-np.expm1(-np.maximum(available,0)/np.array(world.gamma)))
        if np.any(hi<lo-1e-12): return None
        hi=np.maximum(hi,lo)
        c=np.array(world.C)-curvature*np.eye(world.n); b=np.array(world.b)+curvature*(lo+hi)
        offset=world.Y0-curvature*float(lo@hi)
        def f(q): return float(offset+b@q+q@c@q)
        def g(q): return b+2*c@q
        start=lo.copy()
        result=minimize(lambda q:-f(q),start,jac=lambda q:-g(q),bounds=list(zip(lo,hi)),method='SLSQP',
            constraints=[dict(type='ineq',fun=lambda q:world.B-world.spend(q),jac=lambda q:-np.array(world.gamma)/(1-q))],
            options=dict(ftol=1e-11,maxiter=200))
        point=np.clip(result.x,lo,hi)
        # Upper bound is valid at any tangent point of the concave envelope.
        upper=f(point)-float(g(point)@point)+linear_support(world,g(point),lo,hi)+1e-9
        if world.spend(point)<=world.B+1e-10:
            candidate=feasible_scale(world,point); value=float(world.Y(candidate))
            if value>lower: lower=value; x=candidate
        evaluated+=1
        return upper,lo,hi
    initial=bound(np.zeros(world.n),np.full(world.n,world.qbar))
    if initial: heapq.heappush(queue,(-initial[0],counter,initial[1],initial[2]))
    while queue and evaluated+2<=max_boxes:
        if -queue[0][0]-lower<=tolerance: break
        negative,_,lo,hi=heapq.heappop(queue)
        if -negative<=lower+tolerance: continue
        axis=int(np.argmax(hi-lo)); midpoint=(lo[axis]+hi[axis])/2
        if hi[axis]-lo[axis]<1e-12:
            heapq.heappush(queue,(negative,counter,lo,hi)); break
        for side in (0,1):
            l=lo.copy(); h=hi.copy()
            if side: l[axis]=midpoint
            else: h[axis]=midpoint
            bounded=bound(l,h)
            if bounded and bounded[0]>lower:
                counter+=1; heapq.heappush(queue,(-bounded[0],counter,bounded[1],bounded[2]))
    upper=max(lower,-queue[0][0]) if queue else lower
    return dict(q=x.tolist(),lower=lower,upper=upper,gap=upper-lower,certified=upper-lower<=tolerance,
                tolerance=tolerance,boxes=evaluated,status='gap_met' if upper-lower<=tolerance else 'work_limit_or_numerical_resolution')
