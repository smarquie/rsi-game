import unittest
from dataclasses import replace
import numpy as np
from rsi_game.v05.config import Config,with_process
from rsi_game.v05.experiments import plan,preflight
from rsi_game.v05.explore import amplitude
from rsi_game.v05.simulation import simulate,commitment
from rsi_game.v05.function_state import FunctionState
from rsi_game.v05.typology import generate
from rsi_game.v05.review import review,fit_local

class LaunchRevisionTests(unittest.TestCase):
    def test_full_cell_preflight(self):
        # Largest parameter support appears in the full preset, but use one
        # representative config per paper cell and the entire stability grid.
        for study in ('core','stability','tuning'):
            p=plan(study,'paper');self.assertEqual(preflight(p['jobs'])['structurally_blocked_exploration'],0)
        p=plan('core','smoke');p['jobs'][0]['config']['w_min']=.4;p['jobs'][0]['config']['commitment_half_width']=.2
        with self.assertRaisesRegex(ValueError,'frozen'):preflight(p['jobs'])
    def test_wide_commitment_can_explore(self):
        c=Config(commitment_half_width=.2,periods=3,multistarts=4,access_starts=1)
        self.assertEqual(amplitude(0,1,1,1,c,.999),.08)
        r=simulate(generate('symmetric'),c)
        self.assertTrue(any(p['updates'] for p in r['periods'][1:]))
        self.assertTrue(all(p['deployment_spending']<=r['world']['B']+1e-8 for p in r['periods']))
    def test_adaptive_width_not_overwritten(self):
        w=generate('symmetric');s=FunctionState(np.array((0,1,0)),.6,(0,1));c=Config(commit='adaptive')
        commitment(s,w,0,c,.3,previous_target=.2)
        self.assertAlmostEqual(s.bounds[0],.2);self.assertAlmostEqual(s.bounds[1],w.qbar)
    def test_signed_reward_does_not_shrink_scale_without_a_drop(self):
        c=Config();w=generate(n=2,Y0=-5);s=FunctionState(np.array((0,1,0)),.5,(0,1));q=.5+.08*np.sin(np.arange(192)*2*np.pi/192);Y=-3+q-.2*q*q
        previous=float(Y.mean());review(s,q,Y,.2,1,1,c,.999,previous,1);self.assertEqual(s.scale,1.)
    def test_adaptive_fit_subtracts_private_price(self):
        c=Config(within_period='adaptive');s=FunctionState(np.array((0,1,0)),.5,(0,1));q=.5+.08*np.sin(np.arange(192)*2*np.pi/192);prices=.2+.02*np.cos(np.arange(192)*2*np.pi/192);Y=1+q-.2*q*q
        expected,_=fit_local(q,Y-prices*(-np.log1p(-q)))
        review(s,q,Y,float(prices.mean()),1,1,c,.999,float(Y.mean()),1,prices=prices)
        np.testing.assert_allclose(s.belief,expected,atol=1e-12)
    def test_random_replicates_and_readiness_seeds(self):
        p=plan('tuning','paper');jobs=[j for j in p['jobs'] if j['world_seed']==0 and j['world']['archetype']=='concave' and j['config']['remedy']=='random_schedule']
        self.assertEqual(len(jobs),4);self.assertEqual(len({j['seed'] for j in jobs}),4)
        self.assertTrue(all(j['world_seed']>=900000 for j in plan('readiness','pilot')['jobs']))

class ReplicationTests(unittest.TestCase):
    def test_replica_means_not_last_seed(self):
        from rsi_game.v05.research_report import average_replicas
        rows=[dict(id=str(i),world_seed=100,improvement=v,fraction=None) for i,v in enumerate((1.,2.,3.,10.))]
        r=average_replicas(rows)
        self.assertEqual(r['improvement'],4.)
        self.assertEqual(r['_replica_ids'],['0','1','2','3'])
        self.assertIsNone(r['fraction'])
        self.assertNotIn('_replica_ids',rows[0])
