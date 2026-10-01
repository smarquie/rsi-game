"""Executable E1-E8 experiment arms from section 6.7; no unreported retuning."""
from dataclasses import replace
from itertools import product
from .params import *


def arms(experiment):
    base=dict(agent=AgentConfig(),tech=TechParams(),protocol=EvalProtocol(),meta=MetaParams(),designer=DesignerChoice())
    def arm(name,**changes): return name,{**base,**changes}
    if experiment=='E1':
        yield arm('baseline'); yield arm('weak_M',agent=base['agent'].edit('c',1,.5))
    elif experiment=='E2':
        for ell in (2.,float('inf')):
            for k in (1,2,5,10,25,None):
                yield arm(f'K_{k}_ell_{ell}',designer=replace(base['designer'],K=k),meta=replace(base['meta'],ell_rho=ell))
            yield arm(f'external_ell_{ell}',designer=replace(base['designer'],promotion='external'),meta=replace(base['meta'],ell_rho=ell))
    elif experiment=='E3':
        for i,k,mode in product(range(5),(1,5),('self','external','oracle')):
            yield arm(f'weak_{ROLES[i]}_K{k}_{mode}',agent=base['agent'].edit('c',i,.5),designer=replace(base['designer'],K=k,promotion='external' if mode=='external' else 'auto',oracle_diagnosis=mode=='oracle'))
    elif experiment=='E4':
        for x,timing,cost in product((2,3,4),('immediate','at_handover'),(0.,.02)):
            yield arm(f'X{x}_{timing}_cost{cost}',designer=replace(base['designer'],edit_class=x,eval_timing=timing),meta=replace(base['meta'],c_anchor=cost))
    elif experiment=='E5':
        for z,k in product((0.,.5,1.5,3.),(.1,.5,1.)):
            yield arm(f'congestion{z}_cost{k}',tech=replace(base['tech'],zeta_phi=z,kappa=k))
    elif experiment=='E6':
        for m,delta,crn in product((50,200,1000),(0.,.005,.02),(False,True)):
            yield arm(f'm{m}_delta{delta}_crn{crn}',designer=replace(base['designer'],m_eval=m,delta=delta,crn=crn))
    elif experiment=='E7':
        for k in (1,2,3): yield arm(f'sparse{k}',designer=replace(base['designer'],k_sparse=k))
    elif experiment=='E8':
        for k,p in product((2,5,10),('auto','gated')): yield arm(f'K{k}_{p}',designer=replace(base['designer'],K=k,promotion=p))
    else: raise ValueError('Choose E1 through E8')
