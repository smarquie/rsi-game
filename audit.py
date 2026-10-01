"""Reproducible numerical checks of the draft's analytical qualifications."""
from dataclasses import replace
from pathlib import Path
import json
import math
from rsi_game.params import *
from rsi_game.equilibrium import solve
from rsi_game.episode import evaluate
from rsi_game.evaluator import score
from rsi_game.grids import decode
from rsi_game.run import dump


def main():
    cfg=AgentConfig(); tech=TechParams(); psi=EvalProtocol(); sol=solve(cfg,tech); ev=evaluate(sol.profile,cfg,tech)
    # Hold outcomes/tokens fixed exactly as Proposition 7's thought experiment.
    # Its proof overlooks that t_E changes when candidate generator capability changes.
    meta=replace(MetaParams(),ell_rho=100.)
    base=score(ev,cfg,psi,cfg,tech,meta); candidate=score(ev,cfg.edit('c',3,2.),psi,cfg,tech,meta)
    # This is an algebraic counterexample conditional on identical outcomes, not a
    # claim that these two configurations induce identical solved equilibria.
    low=replace(psi,anchor=.01)
    s1=score(ev,cfg,low,cfg,tech); s0=score(ev,cfg,replace(low,anchor=0),cfg,tech)
    gains=[]
    for j in range(5):
        eps=math.log(1.1); new=cfg.edit('c',j,1.1).edit('o',j,.02+.02*eps)
        newsol=solve(new,tech,sol.profile)
        gains.append(float(evaluate(newsol.profile,new,tech).welfare[0]-ev.welfare[0]))
    output=dict(proposition7_conditional_counterexample=dict(ell_rho=100.,incumbent_generator=1.,candidate_generator=2.,
        incumbent_score=base.exact,candidate_score=candidate.exact,incumbent_rho=base.rho_E,candidate_rho=candidate.rho_E,
        incumbent_detection=base.t_E,candidate_detection=candidate.t_E,qualification='Outcome distribution and tokens held fixed algebraically; induced equilibrium equality not asserted'),
        proposition8_boundary_stall=dict(anchor=.01,gain_to_zero=s0.exact-s1.exact,margin=.005,accepted=s0.exact-s1.exact>.005),
        calibration=dict(Q=float(ev.Q[0]),inside_quality_range=.35<=ev.Q[0]<=.65,ten_percent_capability_gains=dict(zip(ROLES,gains)),
            some_gain_exceeds_margin=max(gains)>.005,parameters_retuned=False))
    path=Path('results/default_object/object_analysis.json')
    if path.exists():
        exact=json.loads(path.read_text())['exhaustive']; table=[]
        for item in exact['pure_equilibria']:
            result=evaluate(item['profile'],cfg,tech)
            table.append(dict(**item,actions=decode(item['profile'])[0].tolist(),Q=float(result.Q[0]),tokens=float(result.T[0]),rounds=float(result.rounds[0]),rejections=float(result.rejections[0])))
        output['equilibria']=table
    dump('results/analytical_audit.json',output)

if __name__=='__main__': main()
