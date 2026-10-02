import unittest
from dataclasses import replace
import numpy as np
from rsi_game.v05.config import Config
from rsi_game.v05.typology import generate,descriptors,ARCHETYPES
from rsi_game.v05.simulation import initial_state,simulate
from rsi_game.v05.deploy import deploy
from rsi_game.v05.access import accessibility,local_geometry
from rsi_game.v05.channels import transfer_path,estimate_transfer,full_fit
from rsi_game.v05.explore import frequencies,fully_nonresonant
from rsi_game.v05.interventions import edit,paired
from rsi_game.v05.diagnostics import decomposition
from rsi_game.v05.world import kappa

class V05Tests(unittest.TestCase):
    def test_deployment_feasible_infeasible_bounds(self):
        for seed in range(1000):
            w=generate(seed=seed);c=Config();s=initial_state(w,c)['states']
            for state in s:state.bounds=(.95,.99)
            d=deploy(w,s,c);self.assertTrue(d['rationed']);self.assertLessEqual(d['spending'],w.B+1e-9)
    def test_exploration_premium(self):
        q=.6+.08*np.sin(2*np.pi*np.arange(192)/192)
        self.assertAlmostEqual(float(np.mean(kappa(q))-kappa(.6)),.0101534234,places=7)
    def test_saddle_geometry(self):
        w=generate('saddle');g=local_geometry(w,[.6,.6]);self.assertAlmostEqual(g['multiplier'],.064,places=10);self.assertAlmostEqual(g['max_transfer_curvature'],.064,places=10)
        self.assertLess(accessibility(w,[.6,.6],1,.2,3)['gain'],1e-8)
        self.assertAlmostEqual(accessibility(w,[.6,.6],2,.1,10)['gain'],.0015,delta=.0001)
    def test_activation(self):
        w=generate('activation_example');q=[.75,0,0]
        self.assertLess(accessibility(w,q,2,.6,8)['gain'],1e-8)
        self.assertGreater(accessibility(w,q,3,.1,10)['gain'],.008)
    def test_corner_clearing_plateau(self):
        from rsi_game.v05.fast import clear
        from rsi_game.v05.deploy import price_flags
        w=generate('activation_example');w=replace(w,C=tuple(map(tuple,-.2*np.eye(3))))
        beliefs=np.array([w.local_coeffs(i,[.75,0,0]) for i in range(3)]);bounds=np.tile((0.,w.qbar),(3,1));paths={0:np.full(192,.75)}
        r=clear(w,beliefs,bounds,paths,192)
        self.assertAlmostEqual(r.price,.15,places=8);self.assertTrue(price_flags(w,beliefs,bounds,r.price,paths,192)['setvalued'])
    def test_channels_budget_and_curvature(self):
        w=generate('saddle');q,u,a=transfer_path(w,[.6,.6],(0,1),192,.001)
        self.assertLess(np.ptp(w.spend(q)),1e-12);est=estimate_transfer(w.Y(q),u)
        self.assertAlmostEqual(est['slope'],0,places=8);self.assertAlmostEqual(est['curvature'],.064,places=6)
    def test_full_identification(self):
        freq=frequencies(5,'fullnr');self.assertEqual(freq,(1,4,10,17,29));self.assertFalse(fully_nonresonant((1,4,10,13,28)))
        w=generate();z=np.full(5,.4);a=np.array([.02,.03,.04,.05,.06]);q=z+a*np.sin(2*np.pi*np.arange(1,193)[:,None]*np.array(freq)/192);fit=full_fit(w.Y(q),freq)
        np.testing.assert_allclose(fit['gradient_dither'],w.grad(z)*a,atol=1e-12)
        np.testing.assert_allclose(fit['C_dither'],np.array(w.C)*np.outer(a,a),atol=1e-12)
    def test_invisible(self):
        w=generate();x=np.full(5,.4);v,_=edit(w,'invisible',x)
        self.assertAlmostEqual(w.Y(x),v.Y(x),places=12);np.testing.assert_allclose(w.grad(x),v.grad(x),atol=1e-12)
        for i in range(5):
            for value in (0,.2,.8):
                q=x.copy();q[i]=value;self.assertAlmostEqual(w.Y(q),v.Y(q),places=12)
    def test_pinned_invisible_learning_records(self):
        c=Config(periods=4,multistarts=4,access_starts=1)
        r=paired(generate(n=3),c,'invisible',pre=2,post=4,pin=True)
        for a,b in zip(r['arms']['01']['periods'],r['arms']['11']['periods']):
            np.testing.assert_allclose(a['beliefs'],b['beliefs'],atol=1e-9)
            self.assertAlmostEqual(a['mean_Y'],b['mean_Y'],places=10)
    def test_descriptors(self):
        for name in ('pipeline','hub','two_camps','redundancy'):self.assertEqual(descriptors(generate(name))['frustration'],0)
        self.assertEqual(descriptors(generate('concave'))['positive_inertia'],0)
        w=generate();d=descriptors(w);p=[3,1,4,0,2];v=replace(w,b=tuple(np.array(w.b)[p]),C=tuple(map(tuple,np.array(w.C)[p][:,p])),gamma=tuple(np.array(w.gamma)[p]),alpha=tuple(np.array(w.alpha)[p]));e=descriptors(v)
        for k in d:self.assertAlmostEqual(d[k],e[k],places=10)
        v=replace(w,b=tuple(np.array(w.b)*3),C=tuple(map(tuple,np.array(w.C)*3)),alpha=tuple(np.array(w.alpha)*3));e=descriptors(v)
        for k in d:self.assertAlmostEqual(d[k],e[k],places=10)
    def test_decomposition(self):
        d=decomposition(1.2,-.2,.9,1.,-.3,.2,.15,.18,.25,1.,.999)
        self.assertAlmostEqual(sum(d['ordered'].values()),d['total'],places=12);self.assertAlmostEqual(sum(d['shapley'].values()),d['total'],places=12)
    def test_remedies_execute(self):
        for remedy in ('baseline','R1','R2','R3','R4','R5','R6','R7','R1+R3','oracle','unreviewed'):
            r=simulate(generate(n=3),Config(periods=2,multistarts=3,access_starts=1,channel_every=1,full_every=1,remedy=remedy));self.assertEqual(len(r['periods']),3)
            self.assertTrue(all(p['deployment_spending']<=r['world']['B']+1e-8 for p in r['periods']))
    def test_zero_exploration_frozen(self):
        r=simulate(generate('saddle'),Config(periods=8,multistarts=4,access_starts=2,eps_dis=0,initial_targets=(.6,.6)))
        self.assertEqual(r['summary']['failure_class'],'B_frozen')
    def test_symmetric_table_and_derivative(self):
        from rsi_game.v05.reduced import symmetric_maps
        for alpha,target in ((0,.6),(.1,.565),(.2,.531),(.3,.499),(.5,.440)):
            r=symmetric_maps(alpha=alpha);self.assertAlmostEqual(r['target'],target,delta=.001)
            self.assertAlmostEqual(r['derivative'],r['numerical_derivative'],places=8)
        self.assertAlmostEqual(symmetric_maps(n=5,alpha=0)['feedback'],.25,places=10)
        self.assertAlmostEqual(symmetric_maps(n=2,alpha=0)['feedback'],1.,places=10)
    def test_new_function_same_initial_state_in_paired_arms(self):
        c=Config(periods=1,multistarts=3,access_starts=1)
        r=paired(generate(n=2),c,'newfunction_active',pre=1,post=1)
        a=r['arms']['10']['periods'][0];b=r['arms']['11']['periods'][0]
        self.assertEqual(a['deployment_q'],b['deployment_q']);self.assertEqual(a['beliefs'],b['beliefs']);self.assertEqual(a['bounds'],b['bounds'])
    def test_paired_identity(self):
        c=Config(periods=2,multistarts=3,access_starts=1);r=paired(generate(n=3),c,'capability',pre=1,post=2)
        e=r['effects'];self.assertAlmostEqual(e['A'],e['Gamma1']-e['Gamma0'],places=12)
        for key in ('00','10'):
            p=r['arms'][key]['periods'];self.assertEqual(p[0]['beliefs'],p[-1]['beliefs']);self.assertEqual(p[0]['targets'],p[-1]['targets'])
if __name__=='__main__':unittest.main()
