"""Behavioral meta-game: diagnosis, proposals, noisy selection, sticky promotion.

This is the draft's greedy benchmark, not a solved Markov-perfect equilibrium.
"""
from dataclasses import asdict, replace
import math
import numpy as np
from .params import AgentConfig, TechParams, EvalProtocol, MetaParams, DesignerChoice, ROLES
from .grids import CANONICAL
from .episode import evaluate, sample_episode
from .equilibrium import solve, team_search, diagnostics
from .evaluator import score, compare


def capability_mean(cfg,j,imp,meta):
    return meta.mu0*math.sqrt(imp[2]*imp[3])/meta.c_ref*max(0,1-cfg.c[j]/meta.c_max)


def diagnose(cfg,profile,protocol,snapshot,tech,meta,choice,rng):
    imp=meta.psi_meta*np.array(snapshot.c); attributed=np.zeros(5,dtype=int); truth=np.zeros(5,dtype=int)
    e=evaluate(profile,cfg,tech); s=score(e,cfg,protocol,snapshot,tech,meta)
    flags=(meta.f_E,(1-s.rho_E)*s.t_E,(1-s.rho_E)*s.t_E*s.qI_imp)
    for _ in range(choice.n_diag):
        episode=sample_episode(profile,cfg,tech,rng); origin=episode['origin']
        if origin is not None: truth[origin]+=1
        anchored=rng.random()<protocol.anchor
        failed=not episode['Y'] if anchored else rng.random()<flags[episode['state']]
        if not failed: continue
        if origin is not None and rng.random()<1-math.exp(-meta.zeta_d*imp[origin]):
            attributed[origin]+=1
        else:
            weights=imp.copy()
            if origin is not None: weights[origin]=0
            attributed[rng.choice(5,p=weights/weights.sum())]+=1
    # Random tie breaking; all-zero observations therefore yield uniform targets.
    order=np.lexsort((rng.random(5),-attributed))
    return list(map(int,order[:choice.k_sparse])),attributed.tolist(),truth.tolist()


def stage_proposal(cfg,targets,imp,meta,choice,rng):
    candidate=cfg; edits=[]
    for j in targets:
        if choice.edit_class==1 or rng.random()<meta.p_cap:
            eps=float(rng.normal(capability_mean(cfg,j,imp,meta),meta.sc))
            candidate=candidate.edit('c',j,cfg.c[j]*math.exp(eps)).edit('o',j,cfg.o[j]+meta.omega_o*max(eps,0))
            edits.append(dict(role=ROLES[j],kind='capability',log_change=eps))
        else:
            dl=float(rng.normal(meta.mu_lam*math.sqrt(imp[2]*imp[3])/meta.c_ref,meta.s_lam))
            dw=float(rng.normal(-meta.mu_w,meta.s_w))
            candidate=candidate.edit('lam',j,float(np.clip(cfg.lam[j]+dl,0,1))).edit('w',j,cfg.w[j]*math.exp(dw))
            edits.append(dict(role=ROLES[j],kind='objective',lambda_change=dl,log_w_change=dw))
    return candidate,edits


def run(seed=0,agent=AgentConfig(),tech=TechParams(),protocol=EvalProtocol(),meta=MetaParams(),designer=DesignerChoice(),*,snapshot=None,freeze=False,rich=True):
    """Seed streams are independent by purpose, including discarded promotion trials.

    Log rows describe post-decision state under the *current* snapshot; promotion
    happens after that row. Pre-state, candidate welfare and snapshot are retained.
    """
    streams=np.random.SeedSequence(seed).spawn(4)
    diagnosis_rng,proposal_rng,measurement_rng,promotion_rng=[np.random.default_rng(s) for s in streams]
    cfg=agent; psi=protocol
    initial_snapshot=snapshot or (AgentConfig(c=(designer.external_capability/meta.psi_meta,)*5) if designer.promotion=='external' else agent)
    snap=initial_snapshot; ref=initial_snapshot; ref_protocol=protocol
    sol=solve(cfg,tech,CANONICAL); pending={}; rows=[]; trial_cycles=0; accepted_changes=[]
    for t in range(designer.n_cycles):
        before=cfg; psi_before=psi; imp=meta.psi_meta*np.array(snap.c)
        epoch=t//designer.K if designer.K else 0
        if designer.selection=='canonical': sol=solve(cfg,tech,CANONICAL)
        ev=evaluate(sol.profile,cfg,tech); w_before=float(ev.welfare[0])
        # Marginal intervention uses the role-specific deterministic mean and includes overhead.
        bottleneck_gains=[]
        if rich or designer.oracle_diagnosis:
            for j in range(5):
                eps=capability_mean(cfg,j,imp,meta)
                test=cfg.edit('c',j,cfg.c[j]*math.exp(eps)).edit('o',j,cfg.o[j]+meta.omega_o*max(eps,0))
                try:
                    test_sol=solve(test,tech,CANONICAL if designer.selection=='canonical' else sol.profile)
                    bottleneck_gains.append(float(evaluate(test_sol.profile,test,tech).welfare[0]-w_before))
                except ValueError: bottleneck_gains.append(None)
        bottleneck=int(np.argmax([g if g is not None else -np.inf for g in bottleneck_gains])) if bottleneck_gains else None
        draw=proposal_rng.random(); pe=meta.p_eval if designer.edit_class>=4 else 0.; pr=meta.p_rule if designer.edit_class>=3 else 0.
        kind='eval' if draw<pe else ('rule' if draw<pe+pr else 'stage')
        cand=cfg; cand_psi=psi; targets=[]; attributed=[0]*5; truth=[0]*5; edits=[]; field=None
        if kind=='stage':
            targets,attributed,truth=diagnose(cfg,sol.profile,psi,snap,tech,meta,designer,diagnosis_rng)
            if designer.oracle_diagnosis:
                targets=list(map(int,np.argsort([-np.inf if g is None else g for g in bottleneck_gains])[::-1][:designer.k_sparse]))
            cand,edits=stage_proposal(cfg,targets,imp,meta,designer,proposal_rng)
        elif kind=='rule':
            sign=int(proposal_rng.choice((-1,1)))
            if proposal_rng.random()<.5:
                cand=replace(cfg,L=max(0,cfg.L+sign)); edits=[dict(kind='L',change=cand.L-cfg.L)]
            else:
                rho=float(np.clip(cfg.rho+sign*meta.delta_rho,0,1))
                # Charge only actual changes, including clipped partial steps.
                oc=max(meta.base_o,cfg.o[4]+meta.o_sep*(cfg.rho-rho)/meta.delta_rho)
                cand=replace(cfg,rho=rho).edit('o',4,oc); edits=[dict(kind='rho',change=rho-cfg.rho)]
        else:
            field='anchor' if proposal_rng.random()<.5 else 'separation'
            step=meta.delta_anchor if field=='anchor' else meta.delta_separation
            value=float(np.clip(getattr(psi,field)+proposal_rng.choice((-1,1))*step,0,1))
            cand_psi=replace(psi,**{field:value}); edits=[dict(kind=field,change=value-getattr(psi,field))]
        inc_score=score(ev,cfg,psi,snap,tech,meta); invalid=False
        try:
            cand_sol=sol if cand==cfg else solve(cand,tech,CANONICAL if designer.selection=='canonical' else sol.profile)
            cand_ev=evaluate(cand_sol.profile,cand,tech); cand_score=score(cand_ev,cand,cand_psi,snap,tech,meta)
            si,sc=compare(inc_score,cand_score,designer,measurement_rng)
            accepted=sc-si>designer.delta
            candidate_w=float(cand_ev.welfare[0])
        except ValueError:
            invalid=True; accepted=False; si=inc_score.exact; sc=None; candidate_w=None
        if accepted:
            if kind=='eval' and designer.eval_timing=='at_handover': pending[field]=getattr(cand_psi,field)
            else: cfg=cand; psi=cand_psi; sol=cand_sol
        after_ev=evaluate(sol.profile,cfg,tech); after_score=score(after_ev,cfg,psi,snap,tech,meta)
        # Reversals: accepted coordinate movement opposite an accepted movement in previous epoch.
        movement={}
        for name in ('c','lam','w','o'):
            for j,(old,new) in enumerate(zip(getattr(before,name),getattr(cfg,name))):
                if abs(new-old)>1e-12: movement[f'{name}_{j}']=new-old
        for name in ('L','rho'):
            if getattr(cfg,name)!=getattr(before,name): movement[name]=getattr(cfg,name)-getattr(before,name)
        for name in ('anchor','separation'):
            if getattr(psi,name)!=getattr(psi_before,name): movement[name]=getattr(psi,name)-getattr(psi_before,name)
        reversal=sum(any(e==epoch-1 and key in old and old[key]*change<0 for e,old in accepted_changes) for key,change in movement.items())
        if movement: accepted_changes.append((epoch,movement))
        row=dict(t=t,epoch=epoch,snapshot_hash=snap.fingerprint,snapshot_c=list(snap.c),configuration=asdict(cfg),protocol=asdict(psi),
                 profile=list(sol.profile),converged=sol.converged,regret=sol.regret,solver=sol.method,
                 Q=float(after_ev.Q[0]),W=float(after_ev.welfare[0]),W_before=w_before,candidate_W=candidate_w,
                 p1=float(after_ev.states[0,0]),pD=float(after_ev.states[0,1]),pW=float(after_ev.states[0,2]),tokens=float(after_ev.T[0]),
                 role_tokens=after_ev.tokens[0].tolist(),rounds=float(after_ev.rounds[0]),rejections=float(after_ev.rejections[0]),
                 score=after_score.exact,reference_score=score(after_ev,cfg,ref_protocol,ref,tech,meta).exact,
                 oracle_score=float(after_ev.Q[0]-meta.lambda_T*after_ev.T[0]),rho_E=after_score.rho_E,J=after_score.J,
                 target_class=kind,targets=[ROLES[j] for j in targets],edits=edits,incumbent_measured=si,candidate_measured=sc,
                 accepted=bool(accepted),invalid_proposal=invalid,false_accept=bool(accepted and candidate_w<w_before-1e-12),
                 false_reject=bool(not accepted and candidate_w is not None and candidate_w>w_before+designer.delta),
                 attributed_counts=attributed,true_failure_counts=truth,bottleneck=ROLES[bottleneck] if bottleneck is not None else None,
                 bottleneck_gains=bottleneck_gains,diagnostic_hit=(bottleneck in targets) if targets and bottleneck is not None else None,
                 reversal_coordinates=reversal,promoted=False,pending_evaluation=dict(pending),promotion_trial_cycles=0)
        if rich and t%designer.diagnostics_every==0:
            row['equilibrium_diagnostics']=diagnostics(cfg,tech,sol.profile)
            team=team_search(cfg,tech,sol.profile); row['team_local_welfare']=team['welfare']
            row['selected_welfare_gap_lower_bound']=team['welfare']-row['W']
        if not freeze and designer.K and (t+1)%designer.K==0:
            if designer.promotion=='auto': snap=cfg; row['promoted']=True
            elif designer.promotion=='gated':
                trial_choice=replace(designer,n_cycles=meta.H_ign)
                endpoints=[]
                for test_snapshot in (cfg,snap):
                    trial=run(int(promotion_rng.integers(0,2**32)),cfg,tech,psi,meta,trial_choice,snapshot=test_snapshot,freeze=True,rich=False)
                    trial_cfg=AgentConfig(**trial[-1]['configuration']); trial_psi=EvalProtocol(**trial[-1]['protocol'])
                    trial_ev=evaluate(trial[-1]['profile'],trial_cfg,tech)
                    endpoints.append(score(trial_ev,trial_cfg,trial_psi,snap,tech,meta))
                old_end,new_end=compare(endpoints[1],endpoints[0],designer,promotion_rng)
                row['promotion_gain_difference']=(new_end-old_end)/meta.H_ign
                if row['promotion_gain_difference']>meta.delta_ign: snap=cfg; row['promoted']=True
                trial_cycles+=2*meta.H_ign; row['promotion_trial_cycles']=2*meta.H_ign
            if pending:
                psi=replace(psi,**pending); pending={}
            row['handover_protocol']=asdict(psi); row['next_snapshot_hash']=snap.fingerprint
            epoch_start=rows[-(designer.K-1)]['W_before'] if designer.K>1 else w_before
            row['epoch_gain_per_cycle']=(row['W']-epoch_start)/designer.K
        rows.append(row)
    return rows
