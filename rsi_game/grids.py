"""Table 2 action grids, ordered lexicographically. Profile = five integer indices."""
from itertools import product
import numpy as np

GRIDS = (
    np.array(list(product((0,.02,.05,.10,.15),(0,.25,.5,.75,1.)))),
    np.array([(x,) for x in (0,.02,.05,.10,.15,.20)]),
    np.array(list(product((0,.02,.05,.10,.15,.20),(0,1)))),
    np.array([(s,p) for s,p in product((0,.02,.05,.10,.15),repeat=2) if s+p <= .2000000001]),
    np.array(list(product((0,.02,.05,.10),(0,.05,.10,.20,.30,.50)))),
)
SHAPE = tuple(map(len, GRIDS))
LOW = (0,)*5
HIGH = tuple(n-1 for n in SHAPE)
CANONICAL = tuple(n//2 for n in SHAPE)


def decode(profiles):
    x = np.asarray(profiles, dtype=int).reshape(-1,5)
    if np.any(x < 0) or np.any(x >= SHAPE): raise ValueError('Action index outside grid')
    return np.column_stack([g[x[:,i]] for i,g in enumerate(GRIDS)])
