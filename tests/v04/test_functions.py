"""Tests mapped to draft T1-T17, plus numerical and semantic edge cases."""
import unittest
import os
from dataclasses import replace
import numpy as np
from rsi_game.v04.world import World,make_world,kappa
from rsi_game.v04.config import Config
from rsi_game.v04.fast import best_response,best_responses,clear
from rsi_game.v04.explore import frequencies,nonresonant,path
from rsi_game.v04.review import fit_local,demodulate
from rsi_game.v04.benchmarks import optimize,informed_equilibrium,kkt,idealized,certify_global
from rsi_game.v04.simulation import simulate
from rsi_game.v04.outside import intervene

class FunctionsTests(unittest.TestCase):
    def test_T01_best_response_dense_grid(self):
        rng=np.random.default_rng(1401); count=1000 if os.environ.get('RSI_FULL_VALIDATION') else 100
        points=100000 if os.environ.get('RSI_FULL_VALIDATION') else 20001
        for _ in range(count):
            G,C=rng.uniform(-3,3,2);alpha=rng.uniform(0,1);w,gamma=rng.uniform(.2,2,2);p=rng.uniform(0,4)
            lo=rng.uniform(0,.7);hi=rng.uniform(lo+.01,.99);grid=np.linspace(lo,hi,points)
            value=lambda q:w*(G*q+C*q*q)+alpha*q-p*gamma*kappa(q)
            answer=best_response(G,C,alpha,w,gamma,p,lo,hi)
            self.assertGreaterEqual(value(answer),np.max(value(grid))-1e-9)
            self.assertLessEqual(abs(answer-grid[np.argmax(value(grid))]),2*(hi-lo)/(points-1)+1e-8)

    def test_T02_monotone_demand(self):
        for C in (-1.,0.,1.):
            demand=[best_response(1,C,.2,1.,1.,p,0,.99) for p in np.linspace(0,4,200)]
            self.assertTrue(np.all(np.diff(demand)<=1e-10))

    def test_vector_response_matches_scalar(self):
        rng=np.random.default_rng(131)
        for p in (0.,.01,.1,1.,100.):
            G=rng.normal(size=100);C=-rng.random(100);alpha=rng.random(100);w=rng.uniform(.1,2,100);gamma=rng.uniform(.1,2,100)
            lo=rng.uniform(0,.2,100);hi=rng.uniform(.4,.999,100);beliefs=np.column_stack((np.zeros(100),G,C));bounds=np.column_stack((lo,hi))
            fast=best_responses(beliefs,alpha,w,gamma,p,bounds)
            slow=np.array([best_response(g,c,a,wi,ga,p,l,h) for g,c,a,wi,ga,l,h in zip(G,C,alpha,w,gamma,lo,hi)])
            np.testing.assert_allclose(fast,slow,atol=1e-11)

    def test_T03_price_clearing_and_infeasible(self):
        world=make_world('concave');beliefs=np.tile((0,1.,-.2),(5,1));bounds=np.tile((0.,world.qbar),(5,1))
        result=clear(world,beliefs,bounds,{},192)
        self.assertLessEqual(result.realized_spending,world.B+1e-9);self.assertLess(result.complementarity,1e-7)
        bounds[:]=(.99,world.qbar);result=clear(world,beliefs,bounds,{},192)
        self.assertEqual(result.status,'price_cap_or_infeasible');self.assertGreater(result.realized_spending,world.B)

    def test_T04_decentralization(self):
        w=make_world('concave',alpha_max=0,seed=7)
        optimum=optimize(w,8)['best'];free=informed_equilibrium(w)
        self.assertTrue(free['converged']);np.testing.assert_allclose(free['q'],optimum['q'],atol=1e-6)
        self.assertAlmostEqual(free['price'],optimum['multiplier'],places=6)

    def test_T05_private_motives(self):
        w=make_world('concave',seed=9);shifted=replace(w,b=tuple(np.array(w.b)+np.array(w.alpha)))
        private=optimize(shifted,8)['best'];team=optimize(w,8)['best'];free=informed_equilibrium(w)
        np.testing.assert_allclose(free['q'],private['q'],atol=1e-6)
        loss=team['Y']-float(w.Y(private['q']));self.assertGreaterEqual(loss,-1e-9);self.assertLessEqual(loss,w.qbar*sum(w.alpha)+1e-8)

    def test_T06_worked_examples(self):
        world=make_world('example1');best=optimize(world,8)['best'];mu=np.sqrt(np.exp(-2)/2)
        np.testing.assert_allclose(best['q'],(1-mu,1-2*mu),atol=1e-7)
        private=informed_equilibrium(make_world('example1',example_motive=.5));np.testing.assert_allclose(private['q'],(1-np.exp(-1),)*2,atol=1e-7)
        w=make_world('example2');solutions=optimize(w,16)['solutions'];values=[s['Y'] for s in solutions]
        self.assertTrue(any(abs(v-.656164490237)<1e-7 for v in values));self.assertTrue(any(abs(v-.500790522267)<1e-6 for v in values))
        diagonal=replace(w,C=((-0.2,0.),(0.,-.2)));ib=optimize(diagonal,8)['best']['q']
        np.testing.assert_allclose(ib,(.579,.471),atol=.001);self.assertAlmostEqual(float(w.Y(ib)),.354,places=3)

    def exploration(self,freq=(1,4,10,13,28),active=None):
        rng=np.random.default_rng(14);w=make_world(seed=13);centers=rng.uniform(.2,.7,5);a=np.full(5,.06);T=192
        active=list(range(5)) if active is None else active
        q=np.tile(centers,(T,1))
        for i in active:q[:,i]=path(centers[i],a[i],freq[i],T,w.qbar)[0]
        return w,centers,a,q,w.Y(q)

    def test_T07_single_identification(self):
        w,z,a,q,Y=self.exploration(active=[2]);fit,diag=fit_local(q[:,2],Y)
        np.testing.assert_allclose(fit,w.local_coeffs(2,z),atol=1e-9);self.assertEqual(diag['rank'],3)

    def test_T08_simultaneous_and_resonance(self):
        self.assertEqual(frequencies(5),(1,4,10,13,28));self.assertTrue(nonresonant(frequencies(12)))
        w,z,a,q,Y=self.exploration()
        for i in range(5):
            fit,_=fit_local(q[:,i],Y);np.testing.assert_allclose(fit[1:],w.local_coeffs(i,z)[1:],atol=1e-9)
            expected=w.local_coeffs(i,z)[0]+.5*sum(w.C[j][j]*a[j]**2 for j in range(5) if j!=i)
            self.assertAlmostEqual(fit[0],expected,places=9)
        w,z,a,q,Y=self.exploration((1,2,3,4,5))
        error=max(abs(fit_local(q[:,i],Y)[0][2]-w.C[i][i]) for i in range(5));self.assertGreater(error,1e-6)

    def test_T09_demodulation(self):
        w,z,a,q,Y=self.exploration((1,2,3,4,5))
        for i in range(5): self.assertAlmostEqual(demodulate(q[:,i],Y),w.grad(z)[i],places=9)

    def test_T10_exploration_cost(self):
        w,z,a,q,Y=self.exploration();self.assertAlmostEqual(float(Y.mean()),float(w.Y(z)+.5*np.diag(w.C)@(a*a)),places=10)

    def test_T11_fixed_background_nonidentification(self):
        w,z,a,q,Y=self.exploration(active=[0]);delta=np.zeros((5,5));delta[0,1]=delta[1,0]=.7
        changed=replace(w,C=tuple(map(tuple,np.array(w.C)+delta)),b=tuple(np.array(w.b)-2*delta@z),Y0=w.Y0+float(z@delta@z))
        np.testing.assert_allclose(w.Y(q),changed.Y(q),atol=1e-12)

    def test_T12_staleness(self):
        w=make_world(seed=4);z=np.linspace(.1,.5,5);q=np.linspace(.2,.8,5)
        for i in range(5):
            others=np.arange(5)!=i;e=w.local_coeffs(i,z)[1]-w.local_coeffs(i,q)[1]
            self.assertAlmostEqual(e,2*np.array(w.C)[i,others]@(z[others]-q[others]),places=12)
            self.assertLessEqual(abs(e),2*sum(abs(np.array(w.C)[i,others]))*max(abs(z[others]-q[others]))+1e-12)

    def test_T13_total_derivative_exact_clearing(self):
        w=make_world('example1');optimum=optimize(w,4)['best'];z=np.array(optimum['q']);beliefs=np.array([w.local_coeffs(i,z) for i in range(2)])
        bounds=np.tile((0.,w.qbar),(2,1));h=1e-4
        values,center=path(z[0],h,1,192,w.qbar);Y=[]
        for value in values:
            result=clear(w,beliefs,bounds,{0:np.array([value])},1);Y.append(float(w.Y(result.q[0])))
        fit,_=fit_local(values,Y);slope=fit[1]+2*fit[2]*z[0]
        expected=w.grad(z)[0]-optimum['multiplier']*w.gamma[0]/(1-z[0]);self.assertAlmostEqual(slope,expected,delta=1e-4)

    def test_T14_fixed_points(self):
        w=make_world('example2')
        for point in optimize(w,12)['solutions']:
            trace=idealized(w,point['q'],periods=20,mu=point['multiplier'])
            np.testing.assert_allclose(trace[-1]['q'],point['q'],atol=1e-6)

    def test_T15_absorption_fixed_multiplier(self):
        w=make_world('example2')
        for point in optimize(w,12)['solutions']:
            if min(point['q'])>1e-6: continue
            trace=idealized(w,np.clip(np.array(point['q'])+.01,0,w.qbar),periods=40,mu=point['multiplier'])
            np.testing.assert_allclose(trace[-1]['q'],point['q'],atol=1e-6)
            lag=[r['Y']-point['multiplier']*(r['spending']-w.B) for r in trace]
            self.assertTrue(np.all(np.diff(lag)>=-1e-10))

    def test_T16_invisible_intervention(self):
        w=World((1.,1.),((-.5,0.),(0.,-.5)),(1.,1.),5.,(0.,0.),(1.,1.));x=np.array((.5,.5))
        delta=np.array(((0.,10.),(10.,0.)));new=replace(w,b=tuple(np.array(w.b)-2*delta@x),C=tuple(map(tuple,np.array(w.C)+delta)),Y0=float(x@delta@x))
        np.testing.assert_allclose(new.grad(x),w.grad(x));self.assertAlmostEqual(new.Y(x),w.Y(x))
        for i in range(2):np.testing.assert_allclose(new.local_coeffs(i,x),w.local_coeffs(i,x))
        # Use an actual stationary point for the absorption claim.
        x=np.array((0.,1-np.exp(-1.5)));w=make_world('example2');mu=kkt(w,x)['multiplier']
        delta=np.array(((0.,-10.),(-10.,0.)));new=replace(w,b=tuple(np.array(w.b)-2*delta@x),C=tuple(map(tuple,np.array(w.C)+delta)),Y0=float(x@delta@x))
        np.testing.assert_allclose(idealized(new,x,20,mu=mu)[-1]['q'],x,atol=1e-7)
        self.assertGreater(optimize(new,12)['best']['Y'],float(new.Y(x)))

    def test_T17_determinism_and_local_review(self):
        w=make_world(seed=3);c=Config(periods=4,multistarts=4,schedule='random')
        from rsi_game.v04.benchmarks import benchmark_bundle
        bench=benchmark_bundle(w,4);provider=lambda world:bench
        a=simulate(w,c,7,provider);b=simulate(w,c,7,provider);self.assertEqual(a,b)
        import inspect
        from rsi_game.v04.review import review
        self.assertNotIn('world',inspect.signature(review).parameters)
        self.assertNotIn('context',inspect.signature(review).parameters)

    def test_jump_mixture_finite_horizon(self):
        w=World((0.,),((1.,),),(1.,),.4,(0.,),(1.,),qbar=.95)
        result=clear(w,np.array(((0.,0.,1.),)),np.array(((0.,.95),)),{},192)
        self.assertEqual(result.status,'finite_horizon_mixture');self.assertAlmostEqual(result.theoretical_spending,w.B,places=7)
        self.assertLessEqual(result.realized_spending,w.B+1e-8);self.assertGreater(result.complementarity,0.)

    def test_certificate_and_resource_limit(self):
        w=make_world('example2');certificate=certify_global(w,tolerance=1e-6,max_boxes=100)
        self.assertTrue(certificate['certified']);self.assertAlmostEqual(certificate['lower'],.656164490237,places=6)
        w=make_world(seed=15);limited=certify_global(w,max_boxes=1,tolerance=1e-12)
        self.assertGreaterEqual(limited['upper'],limited['lower']);self.assertEqual(limited['certified'],limited['gap']<=1e-12)

    def test_skip_bounds_ration_and_outside(self):
        w=make_world();c=Config(periods=3,multistarts=2,a_max=.03,w_min=.1)
        result=simulate(w,c);self.assertEqual(result['summary']['skipped_turns'],3)
        self.assertTrue(all(not row['explorers'] for row in result['periods']))
        bounds=np.tile((.9,.95),(5,1));beliefs=np.tile((0.,1.,0.),(5,1))
        ration=clear(w,beliefs,bounds,{},192,budget_rule='ration')
        self.assertGreater(ration.bound_violations,0);self.assertLessEqual(ration.realized_spending,w.B+1e-9)
        result=simulate(w,Config(periods=3,multistarts=2,outside_kind='invisible',outside_period=2))
        self.assertEqual(len(result['world_versions']),2);self.assertLess(abs(result['periods'][2]['outside_event']['target_Y_change']),1e-10)

if __name__=='__main__':unittest.main()
