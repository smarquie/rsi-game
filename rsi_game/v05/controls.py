"""Independent learning control, scored in the original interacting world."""
from dataclasses import replace
import numpy as np
from .simulation import simulate
from .benchmarks import optimize
from .deploy import persistent_time
from .access import audit,local_geometry
from .diagnostics import classify
from .typology import descriptors

def independent(world,config,seed):
    diagonal=replace(world,C=tuple(map(tuple,np.diag(np.diag(world.C)))))
    result=simulate(diagonal,config,seed);bench=optimize(world,config.multistarts,seed);V=bench['best']['Y'];rows=result['periods'];base=float(world.Y(rows[0]['deployment_q']));H=max(0,V-base)
    for row in rows:
        y=float(world.Y(row['deployment_q']));row['training_deployment_Y']=row['deployment_Y'];row['deployment_Y']=y;row['improvement']=y-base;row['opportunity']=max(0,V-y);row['fraction']=(y-base)/H if H>1e-9 else None
    summary=result['summary'];last=rows[-1];ta=persistent_time([r['improvement'] for r in rows],config.absolute_target,config.persistence);tf=persistent_time([r['fraction'] for r in rows],config.fraction_target,config.persistence) if H>1e-9 else None
    ac=audit(world,last['deployment_q'],config.access_starts)
    summary.update(initial_Y=base,final_Y=last['deployment_Y'],improvement=last['improvement'],opportunity=last['opportunity'],fraction=last['fraction'],headroom=H,best_found_Y=V,global_certified=bench['global_certified'],tau_absolute=ta,tau_fraction=tf,tau_absolute_evaluations=rows[ta]['evaluations'] if ta is not None else None,tau_fraction_evaluations=rows[tf]['evaluations'] if tf is not None else None,tau_absolute_resources=rows[ta]['resources'] if ta is not None else None,tail_std=float(np.std([r['deployment_Y'] for r in rows[-config.oscillation_window:]])),failure_class=classify(rows,H,config,ac),**local_geometry(world,last['deployment_q']))
    result.update(benchmark=bench,world=world.to_dict(),descriptors=descriptors(world),accessibility=[dict(period=config.periods,**ac)],information='Trained on diagonal C; deployed configurations evaluated under true interacting Y. Training-period rewards remain diagonal-world measurements.')
    return result
