from dataclasses import replace
import numpy as np


def intervene(world,kind,targets,rng,config):
    c=np.array(world.C); b=np.array(world.b); gamma=np.array(world.gamma); y0=world.Y0
    if kind in ('random','invisible'):
        delta=np.zeros_like(c); idx=np.triu_indices(world.n,1)
        delta[idx]=rng.normal(0,config.outside_scale,len(idx[0])) if kind=='random' else rng.uniform(0,config.outside_scale,len(idx[0]))
        delta+=delta.T; c+=delta
        if kind=='invisible':
            x=np.asarray(targets); b-=2*delta@x; y0+=float(x@delta@x)
    elif kind=='local': b[config.outside_role]+=config.outside_local_gain
    elif kind=='cost': gamma[config.outside_role]*=1-config.outside_cost_fraction
    else: raise ValueError('Unknown outside intervention')
    return replace(world,C=tuple(map(tuple,c)),b=tuple(b),gamma=tuple(gamma),Y0=y0)
