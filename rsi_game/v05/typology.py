"""Seeded structural archetypes and permutation/scale-invariant descriptors."""
from itertools import product
import numpy as np
from .world import World, make_world, kappa
ARCHETYPES=('independent','concave','pipeline','hub','modular','two_camps','redundancy','frustrated','activation')
PROFILES=('uniform','dominant','aligned','anti_aligned')

def _generate(archetype='frustrated',profile='uniform',n=5,seed=0,strength=.4,budget_factor=1.,alpha_max=.3,t=None):
    if '_to_' in archetype:
        if t is None or not 0<=t<=1:raise ValueError('Continuation requires t in [0,1]')
        left,right=archetype.split('_to_');a=generate(left,profile,n,seed,strength,budget_factor,alpha_max);b=generate(right,profile,n,seed,strength,budget_factor,alpha_max)
        from dataclasses import replace
        return replace(a,b=tuple((1-t)*np.array(a.b)+t*np.array(b.b)),C=tuple(map(tuple,(1-t)*np.array(a.C)+t*np.array(b.C))))
    rng=np.random.default_rng(np.random.SeedSequence([seed,505])); c=np.diag(-rng.uniform(.1,.6,n))
    if archetype in ('example1','example2'): return make_world(archetype,seed=seed,budget_factor=budget_factor)
    if archetype in ('saddle','activation_example'):
        if archetype=='saddle': return World((1,1),((-.2,-.5),(-.5,-.2)),(1,1),float(2*kappa(.6)),(0,0),(1,1))
        return World((1,.15,.15),((-.2,0,0),(0,-.2,1.2),(0,1.2,-.2)),(1,1,1),float(kappa(.75)),(0,0,0),(1,1,1))
    if archetype=='symmetric':
        return World((1,)*n,tuple(map(tuple,-.3*np.eye(n))),(1,)*n,float(n*kappa(.6)*budget_factor),(alpha_max,)*n,(1,)*n)
    if archetype not in ARCHETYPES+('broad',): raise ValueError(archetype)
    groups=np.arange(n)//max(1,(n+1)//2)
    for i in range(n):
        for j in range(i+1,n):
            v=rng.uniform(.5,1.5)*strength
            if archetype=='independent': v=0.
            elif archetype=='pipeline': v*=j==i+1
            elif archetype=='hub': v*=i==0
            elif archetype=='modular': v*=groups[i]==groups[j]
            elif archetype=='two_camps': v*=1 if groups[i]==groups[j] else -1
            elif archetype=='redundancy': v=-rng.uniform(1,2)*strength if i%2==0 and j==i+1 else 0.
            elif archetype=='activation': v=rng.uniform(1.5,2.5)*strength if i>=(n//2) else 0.
            elif archetype in ('frustrated','concave'): v=rng.normal(0,strength)
            elif archetype=='broad': v*=rng.choice((-1,1))*(rng.random()<.5)
            c[i,j]=c[j,i]=v
    if archetype=='concave': c-=np.eye(n)*max(0,np.linalg.eigvalsh(c)[-1]+.05)
    b=rng.uniform(.5,1.5,n)
    if profile=='uniform': b[:]=1.
    elif profile=='dominant': b[:]=1.; b[seed%n]=3.
    elif profile in ('aligned','anti_aligned'):
        # Positive value profiles: rank b by absolute top-eigenvector loading.
        # A signed rotation can create negative b; this explicitly documented
        # positive-profile convention avoids that unspecified change of model.
        order=np.argsort(abs(np.linalg.eigh(c)[1][:,-1])); values=np.sort(b)
        b[order]=values if profile=='aligned' else values[::-1]
    else: raise ValueError(profile)
    if archetype=='activation': b[n//2:]=rng.uniform(.05,.25,n-n//2)
    gamma=rng.uniform(.5,1.5,n)
    return World(tuple(b),tuple(map(tuple,c)),tuple(gamma),float(budget_factor*sum(gamma)*kappa(.6)),tuple(rng.uniform(0,alpha_max,n)),(1.,)*n)

def descriptors(world):
    c=np.array(world.C); b=np.array(world.b); n=world.n; off=c-np.diag(np.diag(c)); vals,vec=np.linalg.eigh(c)
    edges=[(i,j,c[i,j]) for i in range(n) for j in range(i+1,n) if c[i,j]!=0]; mass=sum(abs(v) for _,_,v in edges)
    frustration=min((sum(abs(v) for i,j,v in edges if signs[i]*signs[j]*v<0) for tail in product((-1,1),repeat=n-1) for signs in [(1,)+tail]),default=0)/mass if mass else 0.
    strength=abs(off).sum(axis=1); diag=abs(np.diag(c)); scale=max(np.linalg.norm(c),1e-300)
    # Top-eigenspace projection handles repeated top eigenvalues invariantly.
    top=vec[:,abs(vals-vals[-1])<1e-10*scale]
    import networkx as nx
    graph=nx.Graph();graph.add_nodes_from(range(n));graph.add_weighted_edges_from((i,j,v) for i,j,v in edges if v>0)
    modularity=float(nx.community.modularity(graph,nx.community.greedy_modularity_communities(graph,weight='weight'),weight='weight')) if graph.number_of_edges() else 0.
    return dict(complement_modularity=modularity,positive_inertia=int(sum(vals>1e-10*scale)),top_curvature=float(vals[-1]/max(diag.mean(),1e-300)),
        coupling_ratio=float(np.mean(strength/np.maximum(diag,1e-300))),interaction_share=float(np.linalg.norm(2*off@np.full(n,.6))/max(np.linalg.norm(b),1e-300)),
        complement_share=sum(v>0 for _,_,v in edges)/max(1,len(edges)),frustration=float(frustration),density=len(edges)/max(1,n*(n-1)/2),
        centralization=float(strength.max()/strength.mean()) if strength.mean() else 0.,value_cv=float(b.std()/abs(b.mean())) if b.mean() else None,
        alignment=float(np.linalg.norm(top.T@b)/max(np.linalg.norm(b),1e-300)),budget_factor=float(world.B/(sum(world.gamma)*kappa(.6))),cost_cv=float(np.std(world.gamma)/np.mean(world.gamma)))


def generate(*args,Y0=0.,**kwargs):
    from dataclasses import replace
    return replace(_generate(*args,**kwargs),Y0=float(Y0))
