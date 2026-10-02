from dataclasses import dataclass, asdict, fields
import hashlib
import json
import math
from . import VERSION

@dataclass(frozen=True)
class Config:
    price_rule: str = 'clearing'
    remedy: str = 'baseline'
    Y_scale: float = .1
    lambda_p: float = .8
    eta_B: float = .1
    motive_margin: float = .01
    step_cap: float = 1.
    channel_every: int = 5
    full_every: int = 25
    channel_amplitude: float = .05
    channel_eta: float = .5
    channel_break: float = .02
    channel_pairs: tuple = ()
    access_every: int = 25
    access_starts: int = 20
    persistence: int = 10
    oscillation_window: int = 100
    absolute_target: float = .01
    fraction_target: float = .5
    pin_targets: tuple | None = None
    learning: bool = True
    periods: int = 300
    T: int = 192  # Automatically increased when required by n/frequencies.
    k: int = 1
    schedule: str = 'rotation'
    frequencies: str = 'nonresonant'
    commitment_half_width: float | None = None
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
    non_disruption: str = 'absolute_drop'  # absolute_drop is a sign-robust sensitivity arm

    def __post_init__(self):
        if self.commitment_half_width is not None and (not math.isfinite(self.commitment_half_width) or self.commitment_half_width<self.w_min/2):raise ValueError('Commitment half-width must respect minimum freedom w_min/2')
        if self.outside_kind!='none' or self.outside_relocate:raise ValueError('Use the v05 paired intervention runner instead of legacy outside_* controls')
        if self.pin_targets is not None:object.__setattr__(self,'pin_targets',tuple(self.pin_targets))
        if self.within_period!='fixed' and (self.price_rule=='integral' or self.remedy in ('R3','R1+R3')):raise ValueError('Integral-period price requires fixed within-period execution')
        if self.price_rule not in ('clearing','ema','integral'): raise ValueError('Invalid price rule')
        if self.remedy not in ('baseline','R1','R2','R3','R4','R5','R6','R7','R1+R3','oracle','unreviewed','random_schedule','adaptive_commit','damping03'): raise ValueError('Invalid remedy')
        if min(self.channel_every,self.full_every,self.access_every,self.access_starts,self.persistence,self.oscillation_window)<1: raise ValueError('Counts must be positive')
        if not 0<=self.lambda_p<1 or not math.isfinite(self.eta_B) or self.eta_B<=0: raise ValueError('Invalid price gain')
        if min(self.Y_scale,self.step_cap,self.channel_amplitude,self.channel_eta,self.channel_break,self.absolute_target)<0: raise ValueError('Negative scale')
        if not 0<self.fraction_target<=1: raise ValueError('Invalid fraction target')
        object.__setattr__(self,'channel_pairs',tuple(tuple(p) for p in self.channel_pairs))
        if self.initial_targets is not None: object.__setattr__(self,'initial_targets',tuple(self.initial_targets))
        for name in ('periods','T','k','multistarts','outside_period','outside_role'):
            if not isinstance(getattr(self,name),int): raise ValueError(f'{name} must be integer')
        if self.periods<0 or min(self.T,self.k,self.multistarts)<1 or self.outside_role<0 or self.outside_period<1:
            raise ValueError('Invalid counts')
        choices=dict(schedule=('rotation','all','random'),frequencies=('nonresonant','resonant','fullnr'),commit=('fixed','adaptive','motive'),
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
        if any(len(p)!=2 or p[0]==p[1] or min(p)<0 or max(p)>=world.n for p in self.channel_pairs): raise ValueError('Invalid channel pairs')
        if self.k>world.n or self.outside_role>=world.n or self.w_min>world.qbar:
            raise ValueError('k/role/width inconsistent with world')
        if self.initial_targets is not None and (len(self.initial_targets)!=world.n or any(not 0<=q<=world.qbar for q in self.initial_targets)):
            raise ValueError('initial_targets must match world dimension and bounds')

    @property
    def commitment_h(self):
        return self.w_min/2 if self.commitment_half_width is None else self.commitment_half_width

    @property
    def hash(self): return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()[:20]


def load_config(path):
    with open(path) as f: d=json.load(f)
    return d.get('world',{}),Config(**d.get('config',{}))


def with_process(config,remedy):
    from dataclasses import replace
    options={'random_schedule':dict(schedule='random'),'adaptive_commit':dict(commit='adaptive'),'damping03':dict(beta=.3)}
    return replace(config,remedy=remedy,**options.get(remedy,{}))
