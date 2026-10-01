from dataclasses import dataclass, asdict, fields
import hashlib
import json
import math
from . import VERSION

@dataclass(frozen=True)
class Config:
    periods: int = 300
    T: int = 192  # Automatically increased when required by n/frequencies.
    k: int = 1
    schedule: str = 'rotation'
    frequencies: str = 'nonresonant'
    w_min: float = .10
    a_max: float = .08
    eps_dis: float = .02
    rho_dis: float = .05
    curvature_floor: float = .05
    beta: float = .7
    phi_mem: float = 1.
    g0: float = 1.
    commit: str = 'fixed'
    within_period: str = 'fixed'  # adaptive = lagged-price draft algorithm
    budget_rule: str = 'price'
    theta_adj: float = .3
    eta_p: float = .5
    p_min: float = 1e-8
    p_max: float = 1000.
    lambda_overload: float = 1.
    price_tol: float = 1e-10
    multistarts: int = 300
    log_executions: bool = False
    outside_kind: str = 'none'
    outside_period: int = 150
    outside_scale: float = .4
    outside_role: int = 0
    outside_local_gain: float = .3
    outside_cost_fraction: float = .3
    outside_relocate: bool = False  # explicit informed intervention, not baseline
    initial_targets: tuple | None = None  # explicit controlled-start variant
    non_disruption: str = 'draft'  # absolute_drop is a sign-robust sensitivity arm

    def __post_init__(self):
        if self.initial_targets is not None: object.__setattr__(self,'initial_targets',tuple(self.initial_targets))
        for name in ('periods','T','k','multistarts','outside_period','outside_role'):
            if not isinstance(getattr(self,name),int): raise ValueError(f'{name} must be integer')
        if self.periods<0 or min(self.T,self.k,self.multistarts)<1 or self.outside_role<0 or self.outside_period<1:
            raise ValueError('Invalid counts')
        choices=dict(schedule=('rotation','all','random'),frequencies=('nonresonant','resonant'),commit=('fixed','adaptive'),
                     within_period=('fixed','adaptive','adaptive_exact'),budget_rule=('price','ration'),
                     outside_kind=('none','random','invisible','local','cost'),non_disruption=('draft','absolute_drop'))
        for name,values in choices.items():
            if getattr(self,name) not in values: raise ValueError(f'{name} must be one of {values}')
        for name in ('w_min','a_max','eps_dis','rho_dis','curvature_floor','g0','eta_p','p_min','p_max','lambda_overload','price_tol','outside_scale','outside_local_gain'):
            value=getattr(self,name)
            if not math.isfinite(value) or value<0: raise ValueError(f'{name} must be finite and nonnegative')
        if min(self.curvature_floor,self.p_min,self.p_max,self.price_tol,self.a_max)<=0 or self.p_min>=self.p_max:
            raise ValueError('Invalid positive scales')
        for name in ('beta','phi_mem','theta_adj'):
            if not 0<getattr(self,name)<=1: raise ValueError(f'{name} must be in (0,1]')
        if not 0<=self.outside_cost_fraction<1: raise ValueError('Cost reduction must be in [0,1)')
        if self.within_period!='fixed' and self.budget_rule=='ration':
            raise ValueError('Adaptive rationing is unspecified; use fixed rationing or adaptive price')

    def validate_world(self,world):
        if self.k>world.n or self.outside_role>=world.n or self.w_min>world.qbar:
            raise ValueError('k/role/width inconsistent with world')
        if self.initial_targets is not None and (len(self.initial_targets)!=world.n or any(not 0<=q<=world.qbar for q in self.initial_targets)):
            raise ValueError('initial_targets must match world dimension and bounds')

    @property
    def hash(self): return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()[:20]


def load_config(path):
    with open(path) as f: d=json.load(f)
    return d.get('world',{}),Config(**d.get('config',{}))
