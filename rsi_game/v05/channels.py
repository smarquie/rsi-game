"""Public-signal transfer estimates and full-frequency identification."""
from itertools import combinations
import numpy as np
from .world import kappa
from .explore import fully_nonresonant

def transfer_path(world,q,pair,T,amplitude):
    i,j=pair; q=np.asarray(q); costs=np.array(world.gamma)*kappa(q)
    cap=np.array(world.gamma)*kappa(world.qbar)
    a=max(0.,min(amplitude,costs[i],costs[j],cap[i]-costs[i],cap[j]-costs[j]))
    u=a*np.sin(2*np.pi*np.arange(1,T+1)/T); trace=np.tile(q,(T,1))
    trace[:,i]=-np.expm1(-(costs[i]+u)/world.gamma[i]);trace[:,j]=-np.expm1(-(costs[j]-u)/world.gamma[j])
    return trace,u,a

def estimate_transfer(Y,u):
    a=float(np.max(abs(u)))
    if a<1e-12:return dict(slope=None,curvature=None,rank=1)
    z=u/a; coef,_,rank,_=np.linalg.lstsq(np.column_stack((np.ones(len(u)),z,z*z)),Y,rcond=None)
    return dict(slope=float(coef[1]/a),curvature=float(2*coef[2]/a**2),rank=int(rank))

def transfer_update(world,q,pair,estimate,eta=.5,symmetry_break=.02):
    q=np.asarray(q); i,j=pair; c=np.array(world.gamma)*kappa(q); cap=np.array(world.gamma)*kappa(world.qbar)
    if estimate['slope'] is None:return q.copy(),0.
    step=eta*estimate['slope']
    if abs(estimate['slope'])<=1e-6 and estimate['curvature']>0:step=symmetry_break if i<j else -symmetry_break
    step=float(np.clip(step,-min(c[i],cap[j]-c[j]),min(c[j],cap[i]-c[i])))
    c[i]+=step;c[j]-=step
    return -np.expm1(-c/np.array(world.gamma)),step

def full_fit(Y,freq):
    if not fully_nonresonant(freq):raise ValueError('Full identification requires a fully non-resonant design')
    T=len(Y); t=2*np.pi*np.arange(1,T+1)/T; n=len(freq)
    if 2*max(freq)>=T/2:raise ValueError('Aliased signature frequencies')
    cols=[np.ones(T)]; labels=[]
    for i,m in enumerate(freq):cols.extend((np.sin(m*t),np.cos(2*m*t)));labels.append(i)
    pairs=list(combinations(range(n),2))
    for i,j in pairs:cols.extend((np.cos((freq[i]-freq[j])*t),np.cos((freq[i]+freq[j])*t)))
    X=np.column_stack(cols); co,_,rank,_=np.linalg.lstsq(X,Y,rcond=None)
    if rank<len(cols):raise ValueError('Rank deficient full design')
    g=np.array([co[1+2*i] for i in range(n)]); C=np.diag([-2*co[2+2*i] for i in range(n)])
    for k,(i,j) in enumerate(pairs):C[i,j]=C[j,i]=(co[1+2*n+2*k]-co[2+2*n+2*k])/2
    return dict(gradient_dither=g.tolist(),C_dither=C.tolist(),Y_center=float(co[0]-.5*np.trace(C)),rmse=float(np.sqrt(np.mean((X@co-Y)**2))),rank=int(rank))
