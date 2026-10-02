"""Truth-only diagnostics, never supplied to private learning reviews."""
from itertools import permutations
import numpy as np
from .fast import best_response

def decomposition(Ghat,Chat,Ge,Gd,C,mu_used,mu0,mu0d,muc,gamma,qbar):
    def X(g,c,p):return best_response(g,c,0,1,gamma,max(0,p),0,qbar)
    chain=[X(Ghat,Chat,mu_used),X(Ge,C,mu_used),X(Gd,C,mu_used),X(Gd,C,mu0),X(Gd,C,mu0d),X(Gd,C,muc)]
    # Additive parameter corrections define the counterfactual for each subset;
    # all 120 orders are evaluated, including interaction effects of the argmax.
    corrections=np.array([[Ge-Ghat,C-Chat,0],[Gd-Ge,0,0],[0,0,mu0-mu_used],[0,0,mu0d-mu0],[0,0,muc-mu0d]])
    cache={}
    for mask in range(32):
        args=np.array([Ghat,Chat,mu_used])+sum((corrections[j] for j in range(5) if mask>>j&1),start=np.zeros(3))
        cache[mask]=X(*args)
    shap=np.zeros(5)
    for order in permutations(range(5)):
        mask=0
        for j in order:new=mask|1<<j;shap[j]+=cache[mask]-cache[new];mask=new
    names=('identification','staleness','motives','exploration_and_lag','belief_price')
    return dict(total=chain[0]-chain[-1],ordered=dict(zip(names,np.diff(-np.array(chain)).tolist())),shapley=dict(zip(names,(shap/120).tolist())),counterfactual_price_floor=0.)

def classify(rows,headroom,config,access):
    tail=rows[-config.persistence:]; delta=.02*max(headroom,0); enough=len(rows)>=config.persistence
    if enough and (all(r['opportunity']<=delta+1e-9 for r in tail) or (headroom>1e-9 and all(r['fraction']>=config.fraction_target for r in tail))):return 'A_success'
    if max(rows[-1]['skip_counts'],default=0)>=3 and rows[-1]['opportunity']>delta:return 'B_frozen'
    y=np.array([r['deployment_Y'] for r in rows[-config.oscillation_window:]])
    if len(y)>=config.oscillation_window and np.std(y)>.01 and np.std(y[len(y)//2:])>.5*np.std(y[:len(y)//2]):return 'C_persistent_oscillation'
    resting=len(y)>=20 and np.ptp(y[-20:])<1e-4 and np.max(np.ptp(np.array([r['deployment_q'] for r in rows[-20:]]),axis=0))<1e-4
    if resting and access['binding'] and access['misallocation'] is not None and access['misallocation']>1e-3:return 'D_unresolved_misallocation'
    if resting and access['kkt_residual']<1e-6:
        curvature=access['max_transfer_curvature']
        if curvature is not None and curvature>1e-6:return 'E_missed_coordination'
        # Numerical failure to find a pair move cannot certify F/G.
        if any(s['m']>=3 and s['rho']==.05 and s['gain']>1e-7 for s in access.get('searches',[])):return 'F_candidate_higher_order'
        if rows[-1]['opportunity']>delta:return 'G_candidate_barrier'
    if enough and all(r['deployment_rationed'] for r in tail):return 'H_resource_infeasibility'
    return 'U_unresolved_or_transient'
