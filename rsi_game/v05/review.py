"""Private review accepts only own settings, aggregate, public price and own types."""
import numpy as np
from .fast import best_response


def fit_local(own_q,Y):
    # Center and scale for conditioning, then convert to the paper's basis.
    q=np.asarray(own_q); Y=np.asarray(Y); center=float(q.mean()); amplitude=float(np.max(abs(q-center)))
    if amplitude<1e-14: return None,dict(rank=1,condition=None)
    u=(q-center)/amplitude; design=np.column_stack((np.ones(len(q)),u,u*u))
    beta,_,rank,singular=np.linalg.lstsq(design,Y,rcond=None)
    if rank<3: return None,dict(rank=int(rank),condition=None)
    C=beta[2]/amplitude**2; G=beta[1]/amplitude-2*C*center; A=beta[0]-G*center-C*center**2
    return np.array((A,G,C)),dict(rank=int(rank),condition=float(singular[0]/singular[-1]),rmse=float(np.sqrt(np.mean((design@beta-Y)**2))))


def demodulate(own_q,Y):
    centered=np.asarray(own_q)-np.mean(own_q); variance=float(centered@centered)
    return float(centered@Y/variance) if variance>1e-25 else None


def review(state,own_q,Y,price,gamma,w,config,qbar,previous_Y,period,prices=None):
    fit_Y=Y if config.within_period=='fixed' else np.asarray(Y)-np.asarray(prices if prices is not None else price)*gamma*(-np.log1p(-np.asarray(own_q)))/w
    fitted,diagnostic=fit_local(own_q,fit_Y)
    if fitted is None: return dict(updated=False,**diagnostic)
    state.belief=(1-config.phi_mem)*state.belief+config.phi_mem*fitted
    mean=float(np.mean(Y)); threshold=(1-config.rho_dis)*previous_Y if config.non_disruption=='draft' else previous_Y-config.rho_dis*abs(previous_Y)
    state.scale=state.scale/2 if mean<threshold else min(1.,2*state.scale)
    G,C=state.belief[1:]
    mu=price/w if config.within_period=='fixed' and config.budget_rule=='price' else 0.
    optimum=best_response(G,C,0.,1.,gamma,mu,0.,qbar)
    old=state.target; state.target+=config.beta*(optimum-state.target)
    half=config.w_min/2 if config.commit=='fixed' else max(config.w_min/2,abs(state.target-old))
    state.bounds=(max(0.,state.target-half),min(qbar,state.target+half))
    state.last_turn=period; state.rank=diagnostic['rank']; state.condition=diagnostic['condition']
    return dict(updated=True,fitted=fitted.tolist(),target_optimum=float(optimum),demodulated_slope=demodulate(own_q,Y),**diagnostic)
