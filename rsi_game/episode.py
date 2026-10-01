"""Vectorized exact Markov recursion, plus an independent stochastic sampler.

The draft does not define first-pass budget overflow. We complete the rule by
requiring the mandatory first pass to fit. Infeasible profiles have no episode.
Solvers restrict deviations to feasible profiles (a generalized Nash constraint).
"""
from dataclasses import dataclass
import numpy as np
from .params import AgentConfig, TechParams
from .grids import decode

@dataclass
class Batch:
    states: np.ndarray
    tokens: np.ndarray
    first_accept: np.ndarray
    rejections: np.ndarray
    rounds: np.ndarray
    qI: np.ndarray
    feasible: np.ndarray
    utilities: np.ndarray
    welfare: np.ndarray

    @property
    def Q(self): return self.states[:,0]
    @property
    def T(self): return self.tokens.sum(axis=1)


def evaluate(profiles, cfg=AgentConfig(), tech=TechParams()):
    actions = decode(profiles)
    bI,sigma,bM,bR,nu,es,ep,bC,f = actions.T
    n = len(actions)
    cost = np.column_stack((bI,bM,bR,es+ep,bC)) + np.array(cfg.o)
    feasible = cost.sum(axis=1) <= tech.B+1e-12
    states = np.zeros((n,3)); tokens = np.zeros((n,5))
    first = np.zeros(n); rejects = np.zeros(n); rounds = np.zeros(n); qis = np.zeros(n)
    A = 1+tech.a_C*(cfg.c[4]/cfg.c[3])**tech.xi*(-np.expm1(-bC/tech.b_bar))
    hD = (1-cfg.rho)*np.exp(-tech.beta_p*ep)*np.power(f,1/A)
    h = np.column_stack((f,hD,tech.eps_W*hD))
    for d,weight in zip(tech.difficulties, tech.probabilities):
        T = cost[:,0].copy()
        qI = (1-tech.gamma_sigma*sigma)*(1-(1-tech.psi[0])*np.exp(-cfg.c[0]*bI/(d*tech.b_bar)))/(1+tech.zeta_phi*T*T)
        qis += weight*qI
        p = np.column_stack((qI, np.zeros(n), 1-qI))
        tau = np.zeros((n,5)); tau[:,0] = cost[:,0]
        def stage(p,T,i):
            b = (bM,bR,es)[i-1]
            c = cfg.c[i]*(1+tech.mu_sigma*sigma) if i in (1,2) else cfg.c[i]
            q = (1-(1-tech.psi[i])*np.exp(-c*b/(d*tech.b_bar)))/(1+tech.zeta_phi*T*T)
            r = tech.eta[i-1]*q; rw = tech.omega[i-1]*q
            return np.column_stack((p[:,0]*q+p[:,1]*r+p[:,2]*rw,p[:,0]*(1-q)+p[:,1]*(1-r),p[:,2]*(1-rw)))
        for i in (1,2,3):
            T += cost[:,i]; tau[:,i] += cost[:,i]; p = stage(p,T,i)
        T += cost[:,4]; tau[:,4] += cost[:,4]
        out = p*(1-h); first += weight*out.sum(axis=1); p *= h
        rej = p.sum(axis=1); nr = np.zeros(n)
        round_cost = nu*cost[:,1]+cost[:,2]+cost[:,3]+cost[:,4]
        for _ in range(cfg.L):
            can = (T+round_cost <= tech.B+1e-12) & (p.sum(axis=1)>0)
            if not can.any(): break
            out += p*(~can)[:,None]; p *= can[:,None]
            alive = p.sum(axis=1); nr += alive
            for i in (1,2,3):
                active = can & ((nu==1) if i==1 else True)
                T += cost[:,i]*active; tau[:,i] += alive*cost[:,i]*active
                moved = stage(p,T,i); p = np.where(active[:,None],moved,p)
            T += cost[:,4]*can; tau[:,4] += alive*cost[:,4]
            out += p*(1-h); p *= h; rej += p.sum(axis=1)
        out += p
        states += weight*out; tokens += weight*tau; rejects += weight*rej; rounds += weight*nr
    Q = states[:,0]
    local = np.column_stack((sigma,np.log1p(bM/tech.b_bar),-rejects,first,tech.chi_C*rejects))
    utilities = Q[:,None]*np.array(cfg.lam)+local*np.array(cfg.w)-tech.kappa*tokens
    W = Q-tech.kappa_T*tokens.sum(axis=1)
    utilities[~feasible] = -np.inf; W[~feasible] = -np.inf
    return Batch(states,tokens,first,rejects,rounds,qis,feasible,utilities,W)


def sample_episode(profile, cfg, tech, rng, d=None):
    bI,sigma,bM,bR,nu,es,ep,bC,f = decode(profile)[0]
    cost = np.array((bI,bM,bR,es+ep,bC))+cfg.o
    if cost.sum()>tech.B+1e-12: raise ValueError('Mandatory first pass exceeds budget')
    if d is None: d = rng.choice(tech.difficulties,p=tech.probabilities)
    T=cost[0]; tau=np.zeros(5); tau[0]=cost[0]
    qI=(1-tech.gamma_sigma*sigma)*(1-(1-tech.psi[0])*np.exp(-cfg.c[0]*bI/(d*tech.b_bar)))/(1+tech.zeta_phi*T*T)
    s=0 if rng.random()<qI else 2; origin=None if s==0 else 0
    def stage(i,s,origin,T):
        c=cfg.c[i]*(1+tech.mu_sigma*sigma) if i in (1,2) else cfg.c[i]
        b=(bM,bR,es)[i-1]
        q=(1-(1-tech.psi[i])*np.exp(-c*b/(d*tech.b_bar)))/(1+tech.zeta_phi*T*T)
        if s==0:
            if rng.random()>=q: return 1,i
            return 0,None
        repair=(tech.eta[i-1] if s==1 else tech.omega[i-1])*q
        return (0,None) if rng.random()<repair else (s,origin)
    for i in (1,2,3):
        T+=cost[i]; tau[i]+=cost[i]; s,origin=stage(i,s,origin,T)
    A=1+tech.a_C*(cfg.c[4]/cfg.c[3])**tech.xi*(1-np.exp(-bC/tech.b_bar))
    hD=(1-cfg.rho)*np.exp(-tech.beta_p*ep)*f**(1/A)
    h=(f,hD,tech.eps_W*hD); rejections=0; rounds=0; first_accept=False
    while True:
        T+=cost[4]; tau[4]+=cost[4]
        flag=rng.random()<h[s]
        if rounds==0: first_accept=not flag
        rejections+=int(flag)
        round_cost=nu*cost[1]+cost[2]+cost[3]+cost[4]
        if not flag or rounds>=cfg.L or T+round_cost>tech.B+1e-12: break
        rounds+=1
        for i in ((1,2,3) if nu else (2,3)):
            T+=cost[i]; tau[i]+=cost[i]; s,origin=stage(i,s,origin,T)
    return dict(Y=int(s==0),state=s,origin=origin,tokens=tau,rejections=rejections,rounds=rounds,first_accept=first_accept)
