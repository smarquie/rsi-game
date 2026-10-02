"""Explicit, frozen plans. Selection worlds and held-out worlds never overlap."""
from dataclasses import asdict,replace
from itertools import product
from .config import Config
from .typology import ARCHETYPES,PROFILES

REMEDIES=('baseline','R1','R2','R3','R4','R5','R6','R7','R1+R3','oracle')
def plan(study='core',preset='pilot',selection=None):
    if preset not in ('smoke','pilot','paper','full'):raise ValueError(preset)
    periods={'smoke':10,'pilot':100,'paper':300,'full':3000}[preset];starts={'smoke':4,'pilot':32,'paper':300,'full':300}[preset]
    count={'smoke':1,'pilot':5,'paper':50,'full':500}[preset];seeds=range(100,100+count);cfg=Config(periods=periods,multistarts=starts,access_starts={'smoke':2,'pilot':5,'paper':20,'full':20}[preset],access_every=25)
    if preset in ('paper','full') and selection is not None and selection.get('preset') not in ('paper','full'):raise ValueError('Publication studies require publication-scale tuning, not smoke/pilot selection')
    jobs=[]
    def add(family,arm,seed,world,config=cfg,**extra):
        jobs.append(dict(id=f'{len(jobs):07d}',family=family,arm=arm,world_seed=seed,seed=seed,world=dict(seed=seed,**world),config=asdict(config),**extra))
    worlds=('concave','frustrated','two_camps','modular')
    if study=='tuning':
        for seed,archetype,remedy in product(range({'smoke':1,'pilot':5,'paper':100,'full':100}[preset]),worlds,REMEDIES):
            add('X5',f'{archetype}_{remedy}',seed,dict(archetype=archetype),replace(cfg,remedy=remedy,periods=min(periods,1000)))
    elif study=='core':
        for seed,a,motive,h,beta,budget in product(seeds,worlds,(0.,.3),(.05,.2),(.3,.7),( .5,1.,2.,3.) if preset=='full' else (1.,)):
            for remedy in ('baseline','R3'):
                add('X1',f'{a}_alpha{motive}_h{h}_beta{beta}_B{budget}_{remedy}',seed,dict(archetype=a,alpha_max=motive,budget_factor=budget),replace(cfg,w_min=2*h,beta=beta,remedy=remedy))
        for seed,a,n,remedy in product(seeds,('modular','two_camps'),(3,5,8,12),('baseline','unreviewed','oracle','independent')):
            add('X2',f'{a}_n{n}_{remedy}',seed,dict(archetype=a,n=n),replace(cfg,remedy='baseline' if remedy=='independent' else remedy),kind='independent' if remedy=='independent' else 'simulation')
        for seed,a,prior in product(seeds,('frustrated','two_camps'),(.5,1.,2.)):
            add('X3',f'{a}_g{prior}',seed,dict(archetype=a),replace(cfg,g0=prior))
        import numpy as np
        for seed,a,rep in product(seeds,('frustrated','two_camps'),range(4 if preset=='full' else 1)):
            start=tuple(np.random.default_rng([seed,rep,505]).uniform(.05,.8,5))
            add('X3',f'{a}_randomstart',seed,dict(archetype=a),replace(cfg,initial_targets=start),replicate=rep)
        for seed,a,kind in product(seeds,('frustrated','modular'),('capability','cost','interference','complementarity','invisible','newfunction_active','newfunction_inactive','coordinator','process')):
            add('X4',f'{a}_{kind}',seed,dict(archetype=a),kind='paired',intervention=kind,pre=min(150,periods//2),post=periods)
        for seed,pin,remedy in product(seeds,(False,True),('baseline','R6','R7','oracle')):
            add('X4',f'invisible_pin{pin}_{remedy}',seed,dict(archetype='frustrated'),replace(cfg,remedy=remedy),kind='paired',intervention='invisible',pre=min(150,periods//2),post=periods,pin=pin)
        for seed,a,remedy in product(seeds,worlds,REMEDIES):
            add('X5',f'{a}_{remedy}',seed,dict(archetype=a),replace(cfg,remedy=remedy))
    elif study=='typology':
        if selection is None:raise ValueError('Typology requires a frozen selection file from tuning')
        repeats={'smoke':1,'pilot':2,'paper':20,'full':20}[preset]
        for a,p,s,b,rep,remedy in product(ARCHETYPES,PROFILES,(.2,.4,.8),(.5,1.,2.),range(repeats),('baseline',*selection['selected'])):
            seed=100+rep
            add('X6',f'{a}_{p}_s{s}_B{b}_{remedy}',seed,dict(archetype=a,profile=p,strength=s,budget_factor=b),replace(cfg,remedy=remedy,periods=min(periods,1000)))
    elif study=='examples':
        for a,remedy in product(('example1','example2','saddle','activation_example'),REMEDIES):
            q={'saddle':(.6,.6),'activation_example':(.75,0,0),'example2':(0,1-__import__('math').exp(-1.5))}.get(a)
            add('examples',f'{a}_{remedy}',100,dict(archetype=a),replace(cfg,remedy=remedy,initial_targets=q))
    elif study=='structural':
        for seed,a,policy in product(range({'smoke':1,'pilot':5,'paper':100,'full':100}[preset]),worlds,('cycle','eps_greedy')):
            add('S_selection',f'{a}_{policy}',seed,dict(archetype=a),kind='structural',policy=policy)
    elif study=='structural-test':
        if selection is None or 'process_edits' not in selection:raise ValueError('Freeze structural selection first')
        for seed,a,k in product(seeds,worlds,range(len(selection['process_edits'])+1)):
            add('S_heldout',f'{a}_prefix{k}',seed,dict(archetype=a),process_edits=selection['process_edits'][:k],selection_costs=selection.get('selection_costs'))
    elif study=='broad':
        for seed,remedy in product(seeds,('baseline',*(selection['selected'] if selection else ('R1','R3','R6')))):
            add('X6_broad',remedy,seed,dict(archetype='broad',strength=(.2,.4,.8)[seed%3],budget_factor=(.5,1.,2.)[(seed//3)%3]),replace(cfg,remedy=remedy,periods=min(periods,1000)))
    elif study=='long':
        if selection is None:raise ValueError('Long-horizon replication requires frozen selection')
        for seed,a,remedy in product(seeds,worlds,('baseline',*selection['selected'])):
            add('X_long',f'{a}_{remedy}',seed,dict(archetype=a),replace(cfg,remedy=remedy,periods=3000 if preset in ('paper','full') else periods))
    elif study=='continuation':
        for seed,route,t,remedy in product(seeds,('frustrated_to_two_camps','concave_to_redundancy'),[j/20 for j in range(21)],('baseline','R3','R6')):
            add('X6_continuation',f'{route}_t{t}_{remedy}',seed,dict(archetype=route,t=t),replace(cfg,remedy=remedy,periods=min(periods,1000)))
    elif study=='stability':
        for n,alpha,h,beta in product((2,3,5,8),(0.,.1,.2,.3,.5),[j/100 for j in range(1,31)],(.3,.7)):
            add('D1',f'n{n}_alpha{alpha}_h{h}_beta{beta}',100,dict(archetype='symmetric',n=n,alpha_max=alpha),replace(cfg,w_min=2*h,beta=beta))
    else:raise ValueError(study)
    return dict(schema='rsi-v05-plan-1',study=study,preset=preset,jobs=jobs,horizons=[h for h in (300,1000,3000) if h<=periods],selection=selection,
        limitations=['No finite grid covers all possible dynamics.','Full R7 assumes an oracle budget-feasibility service.','Negative accessibility searches do not certify impossibility.'])
