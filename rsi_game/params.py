"""Immutable model parameters. Draft defaults are preserved, not silently calibrated."""
from dataclasses import dataclass, asdict, replace
from hashlib import sha256
import json
import math

ROLES = ('I', 'M', 'R', 'G', 'C')

@dataclass(frozen=True)
class TechParams:
    B: float = 1.0
    difficulties: tuple = (0.5, 1.0, 2.0)
    probabilities: tuple = (1/3, 1/3, 1/3)
    zeta_phi: float = 1.5
    b_bar: float = .05
    psi: tuple = (.6, .4, .4, .5)
    gamma_sigma: float = .15
    mu_sigma: float = .5
    eta: tuple = (.2, .4, .2)
    omega: tuple = (0., 0., 0.)
    eps_W: float = 0.
    a_C: float = 3.
    xi: float = 1.
    beta_p: float = 10.
    kappa: float = .5
    kappa_T: float = .5
    chi_C: int = 1

    def __post_init__(self):
        for name in ('difficulties', 'probabilities', 'psi', 'eta', 'omega'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if len(self.difficulties) != len(self.probabilities) or not self.difficulties:
            raise ValueError('Difficulty distribution must have matching nonempty arrays')
        if any(d <= 0 or not math.isfinite(d) for d in self.difficulties):
            raise ValueError('Difficulties must be finite and positive')
        if any(p < 0 for p in self.probabilities) or not math.isclose(sum(self.probabilities), 1.):
            raise ValueError('Probabilities must be nonnegative and sum to one')
        if len(self.psi) != 4 or len(self.eta) != 3 or len(self.omega) != 3:
            raise ValueError('Wrong technology vector length')
        if any(not 0 <= x <= 1 for x in (*self.psi, *self.eta, *self.omega, self.eps_W, self.gamma_sigma)):
            raise ValueError('Probability coefficients must lie in [0,1]')
        if self.B <= 0 or self.b_bar <= 0 or min(self.zeta_phi, self.mu_sigma, self.a_C, self.xi, self.beta_p, self.kappa, self.kappa_T) < 0:
            raise ValueError('Invalid technology parameters')
        if self.chi_C not in (-1, 1):
            raise ValueError('chi_C must be -1 or +1')

@dataclass(frozen=True)
class AgentConfig:
    c: tuple = (1.,)*5
    lam: tuple = (.7,)*5
    w: tuple = (.05, .05, .05, .10, .05)
    o: tuple = (.02,)*5
    rho: float = .5
    L: int = 3

    def __post_init__(self):
        for name in ('c', 'lam', 'w', 'o'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
            if len(getattr(self, name)) != 5 or not all(math.isfinite(x) for x in getattr(self, name)):
                raise ValueError('Agent vectors must contain five finite values')
        if min(self.c) <= 0 or min(self.w + self.o) < 0 or any(not 0 <= x <= 1 for x in self.lam):
            raise ValueError('Invalid role parameters')
        if not 0 <= self.rho <= 1 or not isinstance(self.L, int) or self.L < 0:
            raise ValueError('Invalid correlation or revision limit')

    def edit(self, name, role, value):
        values = list(getattr(self, name)); values[role] = float(value)
        return replace(self, **{name: tuple(values)})

    @property
    def fingerprint(self):
        return sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]

@dataclass(frozen=True)
class EvalProtocol:
    anchor: float = .3
    separation: float = .3

    def __post_init__(self):
        if not 0 <= self.anchor <= 1 or not 0 <= self.separation <= 1:
            raise ValueError('Evaluation controls must lie in [0,1]')

@dataclass(frozen=True)
class MetaParams:
    psi_meta: float = .8
    zeta_d: float = 1.5
    mu0: float = .10
    sc: float = .15
    c_ref: float = .8
    c_max: float = 4.
    omega_o: float = .02
    mu_lam: float = .03
    s_lam: float = .05
    mu_w: float = .10
    s_w: float = .20
    p_cap: float = .6
    p_rule: float = .10
    p_eval: float = .15
    delta_rho: float = .1
    o_sep: float = .03
    base_o: float = .02
    delta_anchor: float = .1
    delta_separation: float = .1
    c_anchor: float = .02
    rho_E0: float = .9
    ell_rho: float = 2.
    zeta_E: float = 2.
    f_E: float = .05
    lambda_T: float = .2
    H_ign: int = 5
    delta_ign: float = 0.

    def __post_init__(self):
        if self.ell_rho == 'Infinity': object.__setattr__(self, 'ell_rho', float('inf'))
        for name, value in asdict(self).items():
            if name == 'ell_rho':
                if not value > 0: raise ValueError('ell_rho must be positive, possibly infinity')
            elif not math.isfinite(value): raise ValueError(f'{name} must be finite')
        if min(self.c_ref,self.c_max,self.delta_rho,self.H_ign) <= 0:
            raise ValueError('Reference capability, frontier, separation step and trial length must be positive')
        if not isinstance(self.H_ign,int): raise ValueError('H_ign must be an integer')
        for name in ('psi_meta','p_cap','p_rule','p_eval','rho_E0','f_E'):
            if not 0 <= getattr(self,name) <= 1: raise ValueError(f'{name} must lie in [0,1]')
        if self.psi_meta == 0 or self.p_rule+self.p_eval > 1:
            raise ValueError('Positive meta discount and valid target probabilities required')
        if min(self.sc,self.s_lam,self.s_w,self.omega_o,self.o_sep,self.base_o,self.delta_anchor,self.delta_separation,self.c_anchor,self.zeta_E,self.zeta_d,self.lambda_T) < 0:
            raise ValueError('Noise, costs, steps and detection powers must be nonnegative')

@dataclass(frozen=True)
class DesignerChoice:
    K: int | None = 5  # None means infinity
    promotion: str = 'auto'
    edit_class: int = 2
    eval_timing: str = 'immediate'
    selection: str = 'warm'
    n_cycles: int = 200
    k_sparse: int = 1
    delta: float = .005
    m_eval: int = 200
    crn: bool = False
    n_diag: int = 50
    exact: bool = False
    oracle_diagnosis: bool = False
    external_capability: float = 1.2  # effective c_imp, after discount
    diagnostics_every: int = 10

    def __post_init__(self):
        if self.K is not None and (not isinstance(self.K, int) or self.K < 1):
            raise ValueError('K must be a positive integer or null (infinity)')
        if self.promotion not in ('auto', 'gated', 'external') or self.edit_class not in (1,2,3,4):
            raise ValueError('Invalid promotion rule or edit class')
        if self.eval_timing not in ('immediate', 'at_handover') or self.selection not in ('warm','canonical'):
            raise ValueError('Invalid timing or selection')
        if not 1 <= self.k_sparse <= 5 or min(self.m_eval, self.n_diag, self.diagnostics_every) < 1 or self.n_cycles < 0 or self.delta < 0:
            raise ValueError('Invalid counts or margin')


def load(path):
    with open(path) as f: raw = json.load(f)
    constructors = dict(tech=TechParams, agent=AgentConfig, protocol=EvalProtocol, meta=MetaParams, designer=DesignerChoice)
    extra = set(raw) - set(constructors)
    if extra: raise ValueError(f'Unknown configuration sections: {extra}')
    return {k: cls(**raw.get(k, {})) for k, cls in constructors.items()}


def save(path, **sections):
    with open(path, 'w') as f: json.dump({k: asdict(v) for k,v in sections.items()}, f, indent=2, allow_nan=False)
