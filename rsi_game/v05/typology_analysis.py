"""Descriptor prediction, leave-archetype-out validation and behavioural clusters.
Models predict numerical classifications; they do not prove mechanisms."""
from pathlib import Path
import csv,json
from collections import defaultdict
import numpy as np
from .storage import atomic
from .research_report import csvfile,interval

def analyze(root):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score
    root=Path(root);out=root/'research';rows=list(csv.DictReader((out/'all_runs.csv').open()));rows=[r for r in rows if r['subarm']=='run']
    if not rows:return atomic(out/'typology_analysis.json',dict(status='no eligible runs'))
    features=[k for k in rows[0] if k.startswith('descriptor_')];rows=[r for r in rows if all(r.get(k) not in ('',None) for k in features)]
    scores=[];predictions=[]
    for process in sorted({r['process'] for r in rows}):
        selected=[r for r in rows if r['process']==process];X=np.array([[float(r[k]) for k in features] for r in selected]);y=np.array([r['failure_class'] for r in selected]);archetypes=np.array([r['archetype'] for r in selected])
        for held in sorted(set(archetypes)):
            train=archetypes!=held;test=~train
            if sum(train)<20 or len(set(y[train]))<2:continue
            models={'multinomial_logit':make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=505)), 'boosted_trees':HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,l2_regularization=1.,random_state=505)}
            base=max(set(y[train]),key=lambda v:sum(y[train]==v));baseacc=float(np.mean(y[test]==base))
            for name,model in models.items():
                model.fit(X[train],y[train]);pred=model.predict(X[test]);clusters=defaultdict(list)
                for i,predicted in zip(np.flatnonzero(test),pred):
                    clusters[selected[i]['world_seed']].append(float(predicted==y[i]));predictions.append(dict(id=selected[i]['id'],process=process,held_archetype=held,model=name,true=y[i],predicted=predicted))
                mean,lo,hi=interval([np.mean(v) for v in clusters.values()]);scores.append(dict(process=process,held_archetype=held,model=name,accuracy=mean,ci_low=lo,ci_high=hi,majority_baseline=baseacc,test_world_clusters=len(clusters),training_runs=int(sum(train))))
    csvfile(out/'descriptor_generalization.csv',scores);csvfile(out/'descriptor_predictions.csv',predictions)
    worlds=defaultdict(lambda:defaultdict(list));labels={}
    for r in rows:
        if r['fraction']!='':worlds[r['world_identity']][r['process']].append([float(r['fraction']),float(r['tail_std'])]);labels[r['world_identity']]=r['archetype']
    worlds={key:{process:np.mean(values,axis=0).tolist() for process,values in methods.items()} for key,methods in worlds.items()}
    processes=sorted(set.intersection(*(set(v) for v in worlds.values()))) if worlds else []
    complete=[k for k,v in worlds.items() if all(p in v for p in processes)]
    cluster_result=dict(status='insufficient common-process coverage',common_processes=processes)
    if len(processes)>=3 and len(complete)>=20:
        X=np.array([sum((worlds[k][p] for p in processes),[]) for k in complete]);X=StandardScaler().fit_transform(X);archetypes=[labels[k] for k in complete];K=min(len(set(archetypes)),len(complete)-1)
        if K>=2:
            groups=KMeans(n_clusters=K,n_init=10,random_state=505).fit_predict(X)
            csvfile(out/'behavioural_clusters.csv',[dict(world_identity=k,archetype=labels[k],cluster=int(g)) for k,g in zip(complete,groups)])
            cluster_result=dict(status='completed',common_processes=processes,worlds=len(complete),clusters=K,adjusted_rand_index=float(adjusted_rand_score(archetypes,groups)))
    occupancy=[]
    for first,second in (('coupling_ratio','frustration'),('coupling_ratio','budget_factor'),('interaction_share','value_cv')):
        unique={r['world_identity']:r for r in rows};values=list(unique.values())
        if not values:continue
        x=np.array([float(r['descriptor_'+first]) for r in values]);y=np.array([float(r['descriptor_'+second]) for r in values]);hist,xe,ye=np.histogram2d(x,y,bins=5)
        for i in range(5):
            for j in range(5):occupancy.append(dict(first=first,second=second,x_low=xe[i],x_high=xe[i+1],y_low=ye[j],y_high=ye[j+1],worlds=int(hist[i,j]),meets_20=bool(hist[i,j]>=20)))
    csvfile(out/'descriptor_occupancy.csv',occupancy)
    atomic(out/'typology_analysis.json',dict(features=features,generalization_cells=len(scores),behavioural=cluster_result,warning='Exploratory fixed-hyperparameter predictions. Confidence intervals cluster by world seed; empty/thin descriptor bins are explicitly reported. No automatic claim of full descriptor coverage.'))
    return out/'typology_analysis.json'
