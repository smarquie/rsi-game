"""World primitives. True parameters are available to the simulator, never reviews."""
from dataclasses import dataclass, asdict, replace
import hashlib
import json
import numpy as np


def kappa(q):
    q = np.asarray(q, dtype=float)
    if np.any(q < 0) or np.any(q >= 1): raise ValueError('Settings must be in [0,1)')
    return -np.log1p(-q)


@dataclass(frozen=True)
class World:
    b: tuple
    C: tuple
    gamma: tuple
    B: float
    alpha: tuple
    w: tuple
    Y0: float = 0.
    qbar: float = 1-1e-6

    def __post_init__(self):
        for name in ('b', 'gamma', 'alpha', 'w'):
            object.__setattr__(self, name, tuple(float(x) for x in getattr(self, name)))
        object.__setattr__(self, 'C', tuple(tuple(float(x) for x in row) for row in self.C))
        n=len(self.b); c=np.array(self.C)
        if n < 1 or c.shape != (n,n) or any(len(getattr(self,k))!=n for k in ('gamma','alpha','w')):
            raise ValueError('World dimensions must agree')
        if not np.allclose(c,c.T,rtol=0,atol=1e-12): raise ValueError('C must be symmetric')
        if not all(np.isfinite(x).all() for x in (self.b,c,self.gamma,self.alpha,self.w)):
            raise ValueError('World parameters must be finite')
        if min(self.gamma+self.w)<=0 or min(self.alpha)<0 or not np.isfinite(self.B) or self.B<=0:
            raise ValueError('Positive costs, weights and budget; nonnegative motives required')
        if not 0<self.qbar<1 or not np.isfinite(self.Y0): raise ValueError('Invalid qbar or Y0')

    @property
    def n(self): return len(self.b)
    @property
    def hash(self): return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()[:20]
    def Y(self,q):
        q=np.asarray(q); return self.Y0+q@self.b+np.einsum('...i,ij,...j->...',q,np.array(self.C),q)
    def grad(self,q): return np.array(self.b)+2*np.asarray(q)@np.array(self.C)
    def spend(self,q): return kappa(q)@self.gamma
    def local_coeffs(self,i,q):
        z=np.asarray(q,dtype=float).copy(); z[i]=0
        return np.array((self.Y(z),self.b[i]+2*np.array(self.C)[i]@z,self.C[i][i]))
    def to_dict(self): return asdict(self)


def make_world(scenario='frustrated',n=5,seed=0,s_off=.4,budget_factor=1.,alpha_max=.3,qref=.6,qbar=1-1e-6,Y0=0.,example_motive=0.):
    rng=np.random.default_rng(np.random.SeedSequence([seed,1701]))
    if scenario in ('example1','example2'):
        return World(b=(1.,.5) if scenario=='example1' else (1.,.8),
            C=((0.,0.),(0.,0.)) if scenario=='example1' else ((-.2,-.9),(-.9,-.2)),
            gamma=(1.,1.),B=(2. if scenario=='example1' else 1.5)*budget_factor,
            alpha=(0.,example_motive),w=(1.,1.),qbar=qbar,Y0=Y0)
    b=rng.uniform(.5,1.5,n); gamma=rng.uniform(.5,1.5,n); alpha=rng.uniform(0,1,n)*alpha_max
    c=np.diag(-rng.uniform(.1,.6,n)); idx=np.triu_indices(n,1)
    if scenario in ('concave','frustrated'): off=rng.normal(0,s_off,len(idx[0]))
    elif scenario=='complements': off=rng.uniform(0,s_off,len(idx[0]))
    elif scenario=='interference': off=rng.uniform(-s_off,0,len(idx[0]))
    else: raise ValueError(f'Unknown world scenario: {scenario}')
    c[idx]=off; c[(idx[1],idx[0])]=off
    if scenario=='concave':
        largest=np.linalg.eigvalsh(c)[-1]
        if largest>-.05: c-=np.eye(n)*(largest+.05)
    return World(tuple(b),tuple(map(tuple,c)),tuple(gamma),float(budget_factor*sum(gamma)*kappa(qref)),tuple(alpha),(1.,)*n,Y0,qbar)
