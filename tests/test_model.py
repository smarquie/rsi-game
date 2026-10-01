import unittest
from dataclasses import replace
import numpy as np
from rsi_game.params import *
from rsi_game.grids import SHAPE, GRIDS, decode, LOW
from rsi_game.episode import evaluate, sample_episode
from rsi_game.equilibrium import solve, regrets
from rsi_game.evaluator import score, compare
from rsi_game.meta import run

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.cfg=AgentConfig(); self.tech=TechParams(); self.rng=np.random.default_rng(831)
        self.profiles=self.rng.integers(SHAPE,size=(100,5))

    def test_grids(self):
        self.assertEqual(int(np.prod(SHAPE)),950400)
        self.assertEqual(SHAPE,(25,6,12,22,24))

    def test_mass_budget_and_vectorization(self):
        for tech in (self.tech,replace(self.tech,omega=(.1,.2,.3),eps_W=.4)):
            ev=evaluate(self.profiles,self.cfg,tech)
            np.testing.assert_allclose(ev.states.sum(axis=1),1,atol=1e-14)
            self.assertTrue((ev.states>=0).all()); self.assertTrue((ev.T<=tech.B+1e-12).all())
            for i,p in enumerate(self.profiles[:20]):
                scalar=evaluate(p,self.cfg,tech)
                np.testing.assert_allclose(ev.states[i],scalar.states[0],atol=1e-14)
                np.testing.assert_allclose(ev.tokens[i],scalar.tokens[0],atol=1e-14)

    def test_oring(self):
        tech=replace(self.tech,eta=(0,0,0),omega=(0,0,0))
        for p in self.profiles[:25]:
            p=p.copy(); p[4]=0; act=decode(p)[0]; bI,sigma,bM,bR,nu,es,ep,bC,f=act
            expected=0.
            for d,w in zip(tech.difficulties,tech.probabilities):
                cumulative=0.; product=1.
                for i,b in enumerate((bI,bM,bR,es)):
                    cumulative+=self.cfg.o[i]+b+(ep if i==3 else 0)
                    c=self.cfg.c[i]*(1+tech.mu_sigma*sigma) if i in (1,2) else self.cfg.c[i]
                    q=(1-(1-tech.psi[i])*np.exp(-c*b/(d*tech.b_bar)))/(1+tech.zeta_phi*cumulative**2)
                    product*=q*(1-tech.gamma_sigma*sigma) if i==0 else q
                expected+=w*product
            self.assertAlmostEqual(evaluate(p,self.cfg,tech).Q[0],expected,places=14)

    def test_interpreter_floor(self):
        ev=evaluate(self.profiles,self.cfg,self.tech)
        self.assertTrue((ev.Q<=ev.qI+1e-14).all())

    def test_correlated_critic(self):
        cfg=replace(self.cfg,rho=1.)
        for profile in self.profiles[:30]:
            profiles=np.tile(profile,(6,1)); profiles[:,4]=(profile[4]//6)*6+np.arange(6)
            ev=evaluate(profiles,cfg,self.tech)
            self.assertTrue((np.diff(ev.Q)<=1e-12).all())
            self.assertTrue((np.diff(ev.T)>=-1e-12).all())

    def test_two_stage_complementarity(self):
        for eta in (0.,.2,1.):
            fn=lambda x,y: x*y+(1-x)*eta*y
            h=1e-4; x=.3; y=.7
            cross=(fn(x+h,y+h)-fn(x+h,y-h)-fn(x-h,y+h)+fn(x-h,y-h))/(4*h*h)
            self.assertAlmostEqual(cross,1-eta,places=7)

    def test_equilibrium_certification(self):
        for cfg in (self.cfg,self.cfg.edit('c',1,.5),replace(self.cfg,rho=1.,L=0)):
            sol=solve(cfg,self.tech)
            self.assertTrue(sol.converged); self.assertLessEqual(regrets(sol.profile,cfg,self.tech).max(),1e-9)

    def test_no_loop_and_rejection_accounting(self):
        cfg=replace(self.cfg,L=0)
        p=(10,2,4,10,11); ev=evaluate(p,cfg,self.tech)
        self.assertAlmostEqual(ev.rounds[0],0)
        self.assertAlmostEqual(ev.first_accept[0]+ev.rejections[0],1)

    def test_infeasible_budget(self):
        cfg=replace(self.cfg,o=(.25,)*5)
        self.assertFalse(evaluate(LOW,cfg,self.tech).feasible[0])
        with self.assertRaises(ValueError): solve(cfg,self.tech)
        with self.assertRaises(ValueError): sample_episode(LOW,cfg,self.tech,self.rng)

    def test_sampler_exact(self):
        cases=[((10,2,5,10,23),self.tech),((0,0,1,0,5),replace(self.tech,omega=(.2,.4,.3),eps_W=.6))]
        for profile,tech in cases:
            ev=evaluate(profile,self.cfg,tech); samples=[]
            for _ in range(16000):
                s=sample_episode(profile,self.cfg,tech,self.rng)
                self.assertEqual(s['origin'] is None,s['Y']==1)
                samples.append([*(int(s['state']==i) for i in range(3)),*s['tokens'],s['rejections'],s['rounds'],s['first_accept']])
            samples=np.array(samples); expected=np.r_[ev.states[0],ev.tokens[0],ev.rejections[0],ev.rounds[0],ev.first_accept[0]]
            se=samples.std(axis=0,ddof=1)/np.sqrt(len(samples))
            self.assertTrue((abs(samples.mean(axis=0)-expected)<=5*se+1e-10).all())

    def test_evaluation_derivatives(self):
        ev=evaluate((14,2,4,10,0),self.cfg,self.tech); meta=MetaParams(); psi=EvalProtocol()
        base=score(ev,self.cfg,psi,self.cfg,self.tech,meta)
        changed=score(ev,self.cfg,replace(psi,anchor=.4),self.cfg,self.tech,meta)
        self.assertAlmostEqual((changed.exact-base.exact)/.1,ev.Q[0]-base.J-meta.c_anchor,places=13)
        self.assertGreater(base.J+meta.c_anchor,ev.Q[0])
        self.assertGreater(score(ev,self.cfg,replace(psi,anchor=.2),self.cfg,self.tech,meta).exact,base.exact)

    def test_measurement_inversion(self):
        from rsi_game.episode import Batch
        cfg=self.cfg; meta=replace(MetaParams(),rho_E0=1.); psi=EvalProtocol(anchor=0,separation=0)
        ev=evaluate(LOW,cfg,self.tech)
        scores=[]
        for q in (.2,.8):
            modified=replace(ev,states=np.array([[q,1-q,0.]]))
            s=score(modified,cfg,psi,cfg,self.tech,meta)
            self.assertAlmostEqual(s.J,1-meta.f_E*q)
            scores.append(s.exact)
        self.assertGreater(scores[0],scores[1])

    def test_crn_exact_pairing(self):
        ev=evaluate(LOW,self.cfg,self.tech); s=score(ev,self.cfg,EvalProtocol(),self.cfg,self.tech)
        x,y=compare(s,s,replace(DesignerChoice(),crn=True),self.rng); self.assertEqual(x,y)

    def test_determinism_snapshot_and_external(self):
        choice=replace(DesignerChoice(),n_cycles=6,K=2)
        a=run(13,designer=choice,rich=False); b=run(13,designer=choice,rich=False)
        self.assertEqual(a,b); self.assertEqual(a[0]['snapshot_hash'],a[1]['snapshot_hash'])
        self.assertEqual(a[1]['next_snapshot_hash'],a[2]['snapshot_hash'])
        external=run(13,designer=replace(choice,promotion='external'),rich=False)
        self.assertEqual(len({r['snapshot_hash'] for r in external}),1)

    def test_sticky_exact_potential(self):
        rows=run(7,designer=replace(DesignerChoice(),K=None,n_cycles=20,exact=True,selection='canonical'),rich=False)
        for a,b in zip(rows,rows[1:]):
            self.assertGreaterEqual(b['score'],a['score']-1e-12)
            if b['accepted']: self.assertGreater(b['score']-a['score'],.005-1e-12)

    def test_deferred_evaluation_and_gated(self):
        choice=replace(DesignerChoice(),K=2,n_cycles=4,edit_class=4,eval_timing='at_handover',exact=True)
        meta=replace(MetaParams(),p_eval=1.,p_rule=0.)
        rows=run(3,designer=choice,meta=meta,rich=False)
        self.assertEqual(rows[0]['protocol'],asdict(EvalProtocol()))
        self.assertEqual(rows[1]['handover_protocol'],rows[2]['protocol'])
        rows=run(2,designer=replace(choice,promotion='gated'),meta=replace(meta,H_ign=2),rich=False)
        self.assertEqual(sum(r['promotion_trial_cycles'] for r in rows),8)

    def test_invalid_meta_and_infinite_manifest(self):
        with self.assertRaises(ValueError): MetaParams(H_ign=0)
        with self.assertRaises(ValueError): MetaParams(ell_rho=0)
        with self.assertRaises(ValueError): MetaParams(p_eval=.9,p_rule=.9)
        self.assertEqual(MetaParams(ell_rho='Infinity').ell_rho,float('inf'))

    def test_logit_fallback_not_claimed_as_equilibrium(self):
        sol=solve(self.cfg,self.tech,LOW,max_sweeps=1,logit_steps=20)
        self.assertFalse(sol.converged)
        self.assertEqual(sol.method,'logit_modal_non_equilibrium')
        self.assertGreaterEqual(sol.regret,0.)

if __name__=='__main__': unittest.main()
