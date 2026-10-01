"""Executions for one fixed, lagged-adaptive or exact-adaptive period."""
import numpy as np
from .fast import clear, best_responses


def execute(world,beliefs,bounds,paths,T,config):
    initial=clear(world,beliefs,bounds,paths,T,config.p_max,config.price_tol,config.budget_rule)
    if config.within_period=='fixed':
        q=initial.q; prices=np.full(T,initial.price); events=initial.jump_events
    else:
        q=initial.q.copy(); prices=np.empty(T); p=initial.price; events=[]
        free=np.array([i for i in range(world.n) if i not in paths],dtype=int)
        previous=initial.q[0].copy()
        for t in range(T):
            if config.within_period=='adaptive_exact':
                exact=clear(world,beliefs,bounds,{i:np.array([values[t]]) for i,values in paths.items()},1,config.p_max,config.price_tol)
                q[t]=exact.q[0]; p=exact.price; events.extend(exact.jump_events)
            else:
                desired=best_responses(beliefs[free],np.array(world.alpha)[free],np.array(world.w)[free],np.array(world.gamma)[free],p,bounds[free])
                q[t,free]=np.clip(previous[free]+config.theta_adj*(desired-previous[free]),bounds[free,0],bounds[free,1])
            prices[t]=p; spending=float(world.spend(q[t]))
            if config.within_period=='adaptive':
                p=float(np.clip(max(p,config.p_min)*np.exp(np.clip(config.eta_p*(spending-world.B)/world.B,-50,50)),config.p_min,config.p_max))
            previous=q[t].copy()
    Y=world.Y(q); spending=world.spend(q)
    overload=max(0.,float(spending.mean()-world.B)) if config.within_period=='fixed' else float(np.maximum(spending-world.B,0).mean())
    free=[i for i in range(world.n) if i not in paths]
    constant=all(np.ptp(q[:,i])<1e-12 for i in free)
    return dict(q=q,Y=Y,spending=spending,prices=prices,price=float(prices.mean()),mean_Y=float(Y.mean()),
                reward=float(Y.mean()-config.lambda_overload*overload),overload=overload,
                fast_status=initial.status,jump_events=events,free_background_constant=constant,
                theoretical_spending=initial.theoretical_spending,
                complementarity=initial.complementarity if config.within_period=='fixed' else float(np.mean(abs(prices*(spending-world.B)))),
                bound_violations=int(np.count_nonzero((q<bounds[:,0]-1e-10)|(q>bounds[:,1]+1e-10))))
