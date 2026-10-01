"""Optional large Monte Carlo validation, matching section 6.9's sample size.

The draft's per-comparison 3-SE rule is reported, not silently loosened. Because
many simultaneous tests can exceed 3 SE by chance, a separate 5-SE family check
is also reported. Deterministic dimensions have a numerical absolute tolerance.
"""
import argparse
import numpy as np
from dataclasses import replace
from rsi_game.params import *
from rsi_game.episode import evaluate, sample_episode
from rsi_game.grids import SHAPE
from rsi_game.run import dump


def main():
    p=argparse.ArgumentParser(); p.add_argument('--profiles',type=int,default=20); p.add_argument('--samples',type=int,default=100000)
    p.add_argument('--output',default='results/sampler_validation.json'); args=p.parse_args()
    if args.profiles<1 or args.samples<2: p.error('Positive profile count and at least two samples required')
    rng=np.random.default_rng(701); results=[]
    labels=['p1','pD','pW','tokens_I','tokens_M','tokens_R','tokens_G','tokens_C','rejections','rounds','first_accept']
    for j in range(args.profiles):
        cfg=AgentConfig(c=tuple(rng.uniform(.5,2.,5)),rho=float(rng.uniform(0,1)),L=int(rng.integers(0,6)))
        tech=TechParams() if j%2==0 else replace(TechParams(),omega=(.1,.2,.1),eps_W=.3)
        profile=tuple(map(int,rng.integers(SHAPE)))
        ev=evaluate(profile,cfg,tech); total=np.zeros(11); squares=np.zeros(11)
        for _ in range(args.samples):
            s=sample_episode(profile,cfg,tech,rng)
            v=np.r_[[s['state']==i for i in range(3)],s['tokens'],s['rejections'],s['rounds'],s['first_accept']].astype(float)
            total+=v; squares+=v*v
        mean=total/args.samples; variance=np.maximum(0,(squares-total*total/args.samples)/(args.samples-1)); se=np.sqrt(variance/args.samples)
        expected=np.r_[ev.states[0],ev.tokens[0],ev.rejections[0],ev.rounds[0],ev.first_accept[0]]
        error=abs(mean-expected); z=error/np.maximum(se,1e-10)
        results.append(dict(profile=list(profile),samples=args.samples,max_standard_errors=float(z.max()),
            comparisons=[dict(metric=label,exact=float(e),sample=float(m),standard_error=float(s),z=float(v)) for label,e,m,s,v in zip(labels,expected,mean,se,z)],
            outside_3se=[labels[i] for i in range(11) if error[i]>3*se[i]+1e-10],outside_5se=[labels[i] for i in range(11) if error[i]>5*se[i]+1e-10]))
        print(f'{j+1}/{args.profiles}: max z={z.max():.3f}',flush=True)
    dump(args.output,dict(seed=701,profiles=args.profiles,samples_per_profile=args.samples,
        all_within_3se=all(not x['outside_3se'] for x in results),all_within_5se=all(not x['outside_5se'] for x in results),results=results))

if __name__=='__main__': main()
