"""Standalone scientific plots; matplotlib is an optional reporting dependency."""
from pathlib import Path
import numpy as np
import os
import tempfile
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'rsi-game-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot_runs(runs,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    for run in runs:
        rows=run['rows'];period=np.array([r['period'] for r in rows]);q=np.array([r['mean_settings'] for r in rows]);targets=np.array([r['targets'] for r in rows])
        fig,axes=plt.subplots(2,2,figsize=(12,7.2),constrained_layout=True)
        fig.suptitle('RSI Functions v0.4 | '+run['name'],fontsize=12)
        for i in range(q.shape[1]):
            color=f'C{i%10}';axes[0,0].plot(period,q[:,i],color=color,label=f'q{i+1}');axes[0,0].plot(period,targets[:,i],color=color,linestyle='--',alpha=.7)
        axes[0,0].set(title='Settings (solid) and targets (dashed)',ylabel='Setting');axes[0,0].legend(ncol=min(5,q.shape[1]),fontsize=7)
        for key,label in (('mean_Y','Raw mean Y'),('reward','Penalized reward'),('best_found_Y','Team best found')):axes[0,1].plot(period,[r[key] for r in rows],label=label)
        axes[0,1].set(title='Outcomes and benchmark',ylabel='Aggregate');axes[0,1].legend(fontsize=8)
        for i in range(q.shape[1]):axes[1,0].plot(period,[abs(r['staleness_error'][i]) for r in rows],label=f'Function {i+1}')
        axes[1,0].set(title='Absolute belief staleness',ylabel='|G belief - G current|')
        axes[1,1].plot(period,[r['exploration_effect'] for r in rows],label='Actual effect')
        axes[1,1].plot(period,[r['predicted_exploration_effect'] for r in rows],linestyle='--',label='Quadratic prediction')
        axes[1,1].set(title='Exploration effect',ylabel='Mean Y - Y at mean settings');axes[1,1].legend(fontsize=8)
        for ax in axes.flat:ax.set_xlabel('Review period');ax.grid(alpha=.2)
        name=run['name'].replace('/','__');fig.savefig(directory/(name+'.svg'));fig.savefig(directory/(name+'.png'),dpi=150);plt.close(fig)


def plot_basin(data,output):
    path=Path(output);points=data['points']
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    x=[p['start'][0] for p in points];y=[p['start'][1] for p in points]
    for ax,key,label in ((axes[0],'nearest_candidate','Nearest stationary candidate (diagnostic)'),(axes[1],'Y','Final aggregate Y')):
        scatter=ax.scatter(x,y,c=[p[key] for p in points],s=32,cmap='viridis',marker='s')
        fig.colorbar(scatter,ax=ax);ax.set(xlabel='Initial q1',ylabel='Initial q2',title=label,xlim=(0,1),ylim=(0,1));ax.set_aspect('equal')
    fig.suptitle(f"Example 4.7 | {data['mode']} | {data['resolution']} × {data['resolution']} initial grid | {data['periods']} periods")
    fig.savefig(path.with_suffix('.svg'));fig.savefig(path.with_suffix('.png'),dpi=150);plt.close(fig)


def plot_family_statistics(family,statistics,directory):
    """Every arm, with world-level means and 95% bootstrap intervals."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    names=sorted({r['arm'] for r in statistics});metrics=('tail_mean_reward','mean_overload','tail_target_range')
    height=max(4.5,.27*len(names)+1.5)
    fig,axes=plt.subplots(1,3,figsize=(18,height),sharey=True,constrained_layout=True)
    for ax,metric in zip(axes,metrics):
        lookup={r['arm']:r for r in statistics if r['metric']==metric}
        for y,name in enumerate(names):
            r=lookup[name]
            if r['mean'] is None:continue
            ax.plot(r['mean'],y,'o',color='#137f77',markersize=4)
            if r['ci95_low'] is not None:ax.plot([r['ci95_low'],r['ci95_high']],[y,y],color='#137f77',linewidth=1.5)
        ax.set_title(metric.replace('_',' '));ax.grid(axis='x',alpha=.2);ax.set_yticks(range(len(names)),names,fontsize=7)
    axes[0].invert_yaxis();fig.suptitle(f'{family} | All completed arms | Means and exploratory 95% world-bootstrap intervals\nSingle-world estimates have no interval; designs and feasibility differ across arms',fontsize=12)
    for ext in ('svg','png'):fig.savefig(directory/f'{family}.{ext}',dpi=150)
    plt.close(fig)
