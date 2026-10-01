"""Equations 19-24. Snapshot c and discounted c_imp are deliberately distinct."""
from dataclasses import dataclass
import numpy as np
from .params import MetaParams

@dataclass(frozen=True)
class Score:
    probability: float
    cost: float
    J: float
    rho_E: float
    t_E: float
    qI_imp: float
    @property
    def exact(self): return self.probability-self.cost


def score(ev,cfg,protocol,snapshot,tech,meta=MetaParams()):
    imp=meta.psi_meta*np.array(snapshot.c)
    distance=sum(abs(a-b) for a,b in zip(cfg.c,snapshot.c))
    rho=meta.rho_E0*(1-protocol.separation)*np.exp(-distance/meta.ell_rho)
    t=1-np.exp(-meta.zeta_E*imp[4]/cfg.c[3])
    qi=1-(1-tech.psi[0])*np.exp(-imp[0])
    p1,pD,pW=ev.states[0]
    J=p1*(1-meta.f_E)+pD*(1-(1-rho)*t)+pW*(1-(1-rho)*t*qi)
    a=protocol.anchor
    return Score(float(a*p1+(1-a)*J),float(meta.lambda_T*ev.T[0]+meta.c_anchor*a),float(J),float(rho),float(t),float(qi))


def compare(inc,cand,choice,rng):
    if choice.exact: return inc.exact,cand.exact
    if choice.crn:
        u=rng.random(choice.m_eval)
        return float(np.mean(u<inc.probability)-inc.cost),float(np.mean(u<cand.probability)-cand.cost)
    return (float(rng.binomial(choice.m_eval,inc.probability)/choice.m_eval-inc.cost),
            float(rng.binomial(choice.m_eval,cand.probability)/choice.m_eval-cand.cost))
