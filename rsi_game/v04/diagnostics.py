"""Calibration audit and finite-resolution two-dimensional basin maps."""
from dataclasses import replace
import numpy as np
from .world import make_world
from .benchmarks import benchmark_bundle,idealized,feasible_scale
from .config import Config
from .simulation import simulate
from .fast import clear


def calibration(worlds=50,starts=300):
    records=[]
    for seed in range(worlds):
        world=make_world(seed=seed); benchmarks=benchmark_bundle(world,starts)
        belief=np.tile((0.,1.,0.),(world.n,1)); q0=clear(world,belief,np.tile((0.,world.qbar),(world.n,1)),{},1).q[0]
        best=benchmarks['team']['best']; candidates=benchmarks['team']['validated_stationary_points']
        records.append(dict(seed=seed,positive_eigenvalues=int(np.count_nonzero(np.linalg.eigvalsh(world.C)>0)),stationary_candidates=len(candidates),
            best_found_Y=best['Y'],initial_Y=float(world.Y(q0)),budget_binds=abs(best['spending']-world.B)<1e-6,
            relative_initial_gap=(best['Y']-float(world.Y(q0)))/max(abs(best['Y']),1e-12),certified=benchmarks['team']['global_certified']))
        print(f'Calibration {seed+1}/{worlds}',flush=True)
    return dict(worlds=worlds,multistarts=starts,share_multiple_candidates=float(np.mean([r['stationary_candidates']>=2 for r in records])),
        share_budget_binding=float(np.mean([r['budget_binds'] for r in records])),share_initial_gap_at_least_5pct=float(np.mean([r['relative_initial_gap']>=.05 for r in records])),
        retuned=False,qualification='Multi-start candidates are not an exhaustive count of local optima; no automatic parameter tuning',records=records)


def basin_map(resolution=21,periods=150,mode='fixed_low'):
    if resolution<2 or periods<1: raise ValueError('At least two grid points and one period required')
    world=make_world('example2'); bench=benchmark_bundle(world,32); candidates=bench['team']['validated_stationary_points']
    multiplier=min(candidates,key=lambda x:x['Y'])['multiplier'] if mode=='fixed_low' else max(candidates,key=lambda x:x['Y'])['multiplier']
    points=[]
    for x in np.linspace(0,world.qbar,resolution):
        for y in np.linspace(0,world.qbar,resolution):
            start=np.array([x,y])
            if world.spend(start)>world.B+1e-12: continue
            if mode=='learning':
                result=simulate(world,Config(periods=periods,multistarts=32,initial_targets=tuple(start)),benchmark_provider=lambda w:bench)
                final=np.array(result['summary']['final_targets']); Y=float(world.Y(final))
            else:
                result=idealized(world,start,periods,mu=multiplier);final=np.array(result[-1]['q']);Y=result[-1]['Y']
            points.append(dict(start=start.tolist(),final=final.tolist(),Y=Y,spending=float(world.spend(final)),
                               nearest_candidate=int(np.argmin([np.max(abs(final-c['q'])) for c in candidates]))))
    return dict(mode=mode,resolution=resolution,periods=periods,mu=multiplier if mode!='learning' else None,candidates=candidates,points=points,
                qualification='Finite grid of initial states; not exhaustive continuous basins. Fixed-multiplier paths need not preserve budget feasibility.')
