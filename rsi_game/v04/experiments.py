"""Predeclared v0.4 E1-E12 plus explicit robustness families R1-R6.

These definitions prepare experiments; importing this module starts no runs.
"""
from dataclasses import dataclass, field, asdict
from itertools import product
from .config import Config
from .explore import executions

@dataclass
class Arm:
    family: str
    name: str
    world: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    question: str = ''


def all_arms():
    a=[]
    def add(family,name,world=None,config=None,question=''):
        a.append(Arm(family,name,world or {},config or {},question))
    for k,beta,width,budget in product((1,2,5),(.3,.7,1.),(.02,.1,.2),(1.,3.)):
        add('E1',f'k{k}_beta{beta}_width{width}_budget{budget}',dict(scenario='concave',budget_factor=budget),dict(k=k,beta=beta,w_min=width), 'Binding versus slack budget convergence; width and damping')
    for scenario,g0,alpha in product(('frustrated','interference'),(.5,1.,2.),(0.,.3,.6)):
        add('E2',f'{scenario}_prior{g0}_alpha{alpha}',dict(scenario=scenario,alpha_max=alpha),dict(g0=g0),'Trap frequency and initial-condition dependence')
    for k,freq in product((1,2,5),('nonresonant','resonant')):
        add('E3',f'k{k}_{freq}',config=dict(k=k,frequencies=freq),question='Exact separation and resonant negative controls')
    for eps,amp in product((.005,.02,.05),(.03,.08,.15)):
        add('E4',f'tolerance{eps}_amplitude{amp}',config=dict(eps_dis=eps,a_max=amp),question='Disruption and skipped-turn feasibility')
    for alpha,width,reviewed in product((0.,.3,.6),(.02,.1,.3),(False,True)):
        add('E5',f'alpha{alpha}_width{width}_reviewed{reviewed}',dict(alpha_max=alpha),dict(w_min=width,**({} if reviewed else {'periods':0})), 'Private motives versus self-commitment')
    for interaction,k,memory in product((.1,.4,.8),(1,5),(.5,1.)):
        add('E6',f'interaction{interaction}_k{k}_memory{memory}',dict(s_off=interaction),dict(k=k,phi_mem=memory),'Staleness, damping of beliefs and oscillations')
    add('E7','fixed',config=dict(within_period='fixed'),question='Fixed background reference')
    for theta in (.1,.3,1.):
        add('E7',f'adaptive_theta{theta}',config=dict(within_period='adaptive',theta_adj=theta),question='Lagged adaptation, budget dynamics and net-gradient learning')
    add('E7','adaptive_exact',config=dict(within_period='adaptive_exact'),question='Exact-clearing control for the total-derivative proposition')
    for scenario in ('concave','complements','interference','frustrated'):
        add('E8',scenario,dict(scenario=scenario),question='Ignoring interactions versus discovered stationary points')
    for kind,k in product(('random','invisible','local','cost'),(1,5)):
        add('E9',f'{kind}_k{k}',config=dict(outside_kind=kind,k=k),question='Local visibility and adaptation after outside changes')
    add('E9','invisible_with_relocation',config=dict(outside_kind='invisible',outside_relocate=True),question='Explicit informed relocation versus locally invisible intervention')
    for n in (3,5,8,12):
        add('E10',f'n{n}',dict(n=n),question='Scale; T automatically respects the frequency constraint')
    for budget in (.5,1.,2.,3.):
        add('E11',f'budget{budget}',dict(budget_factor=budget),question='Budget tightness and distance-to-perfection pattern')
    add('E12','linear',dict(scenario='example1'),question='Example 4.6')
    add('E12','linear_private_motive',dict(scenario='example1',example_motive=.5),question='Example 5.11')
    add('E12','interference_left',dict(scenario='example2'),dict(initial_targets=(.7768698398515702,0.)), 'Example 4.7 left controlled start; finite-width learning variant')
    add('E12','interference_right',dict(scenario='example2'),dict(initial_targets=(0.,.7768698398515702)), 'Example 4.7 right controlled start; finite-width learning variant')
    for kind,k in product(('rotation','random','all'),(1,2,5)):
        if kind=='all' and k!=5: continue
        add('R1',f'{kind}_k{k}',config=dict(schedule=kind,k=k),question='Architectural schedule and true replication randomness')
    for budget_rule,commit in product(('price','ration'),('fixed','adaptive')):
        add('R2',f'{budget_rule}_{commit}',config=dict(budget_rule=budget_rule,commit=commit),question='Rationing bounds conflict and adaptive commitment')
    for eta,theta in product((.1,.5,1.),(.1,.3,1.)):
        add('R3',f'eta{eta}_theta{theta}',config=dict(within_period='adaptive',eta_p=eta,theta_adj=theta),question='Price-adjustment instability and overload')
    for offset,rule in product((-5.,0.,5.),('draft','absolute_drop')):
        add('R4',f'offset{offset}_{rule}',dict(Y0=offset),dict(non_disruption=rule), 'Translation/sign sensitivity of disruption rules')
    for width,amp in product((0.,.02,.1,.3),(.03,.08,.15)):
        add('R5',f'width{width}_amplitude{amp}',config=dict(w_min=width,a_max=amp),question='Exploration shutdown boundary and zero-width commitment control')
    for budget,beta in product((.5,1.,3.),(.1,.7,1.)):
        add('R6',f'all_budget{budget}_beta{beta}',dict(budget_factor=budget),dict(k=5,schedule='all',beta=beta), 'No free price-responsive functions: slack price versus overload')
    return a

PRESETS={
    'smoke':dict(worlds=1,replicates=1,periods=12,multistarts=8),
    'pilot':dict(worlds=5,replicates=1,periods=100,multistarts=32),
    'full':dict(worlds=50,replicates=4,periods=300,multistarts=300),
}


def plan(preset='pilot',families=None,worlds=None,replicates=None,periods=None,multistarts=None,keep_duplicates=False):
    settings=PRESETS[preset].copy()
    for key,value in dict(worlds=worlds,replicates=replicates,periods=periods,multistarts=multistarts).items():
        if value is not None: settings[key]=value
    if min(settings['worlds'],settings['replicates'],settings['multistarts'])<1 or settings['periods']<0: raise ValueError('Invalid plan counts')
    arms=all_arms()
    if families: arms=[a for a in arms if a.family in families]
    if not arms: raise ValueError('No matching experiment families')
    if preset=='smoke':
        selected=[]
        for family in dict.fromkeys(a.family for a in arms):
            group=[a for a in arms if a.family==family]
            # Include first/last to cover boundary and non-baseline branches.
            selected.extend([group[0]]+([group[-1]] if len(group)>1 else []))
        arms=selected
    jobs=[]; descriptions=[]
    for arm in arms:
        world_options=dict(scenario='frustrated',n=5,s_off=.4,budget_factor=1.,alpha_max=.3,**{})
        world_options.update(arm.world)
        n=2 if world_options['scenario'].startswith('example') else world_options['n']
        changes=dict(periods=settings['periods'],multistarts=settings['multistarts'])
        changes.update(arm.config)
        if changes.get('outside_kind','none')!='none': changes['outside_period']=max(1,changes['periods']//2)
        config=Config(**changes)
        stochastic=config.schedule=='random' or config.outside_kind in ('random','invisible')
        repetitions=settings['replicates'] if stochastic or keep_duplicates else 1
        world_count=1 if world_options['scenario'].startswith('example') else settings['worlds']
        notes=[]
        if config.a_max<config.w_min/2: notes.append('All scheduled turns necessarily skip: a_max < w_min/2')
        if config.w_min==0: notes.append('Zero-width idealization; not the default minimum-freedom model')
        if config.k==n or config.schedule=='all': notes.append('During all-explorer periods price cannot adjust any free setting')
        if config.budget_rule=='ration': notes.append('Physical rationing may violate commitment lower bounds; violations logged')
        if not stochastic and settings['replicates']>1 and not keep_duplicates: notes.append('Identical deterministic seed replicas deduplicated')
        descriptions.append(dict(family=arm.family,name=arm.name,question=arm.question,worlds=world_count,replicates=repetitions,notes=notes,
                                 T=executions(n,config.T,config.frequencies),config=asdict(config),world=world_options))
        for world_index in range(world_count):
            for replicate in range(repetitions):
                jobs.append(dict(family=arm.family,arm=arm.name,world_seed=world_index,seed=replicate,
                                 world=world_options,config=asdict(config)))
    # Execution-count estimate excludes SLSQP iterations and the truth-only oracle
    # benchmark; runtime is deliberately estimated only after measured pilot jobs.
    total_executions=sum((j['config']['periods']+1)*executions(2 if j['world']['scenario'].startswith('example') else j['world']['n'],j['config']['T'],j['config']['frequencies']) for j in jobs)
    return dict(preset=preset,settings=settings,arms=descriptions,jobs=jobs,job_count=len(jobs),arm_count=len(arms),
                total_model_executions=total_executions,keep_deterministic_duplicates=keep_duplicates,
                statistical_unit='world; random schedule/intervention replicas are nested within world',
                scope='Prepared finite experimental design, not exhaustive continuous state-space dynamics')
