import csv
import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
from rsi_game.v04.config import Config
from rsi_game.v04.storage import run_job,job_path,atomic_json
from rsi_game.v04.research_report import build,stats
from rsi_game.v04.analysis import metrics

class ResearchReporting(unittest.TestCase):
    def test_intervals_preserve_missingness(self):
        self.assertEqual(stats([None])['n'],0)
        self.assertIsNone(stats([2])['ci95_low'])
        self.assertEqual(stats([2,2,2])['ci95_high'],2)

    def test_all_runs_world_weighting_coverage_and_contrasts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'study';out=Path(tmp)/'report';jobs=[]
            # Synthetic outcome edits isolate reporting arithmetic from model behavior.
            for world,seed,Y in ((0,0,10),(0,1,30),(1,0,100)):
                job=dict(family='E7',arm='fixed',world_seed=world,seed=seed,world=dict(scenario='example1'),config=asdict(Config(periods=0,multistarts=2)))
                run_job(job,root);jobs.append(job)
                p=job_path(root,job)/'summary.json';summary=json.loads(p.read_text());summary['final_Y']=Y;atomic_json(p,summary)
            missing=dict(jobs[0],arm='adaptive_exact');atomic_json(root/'plan.json',dict(jobs=jobs+[missing],arms=[]))
            spec=Path(tmp)/'contrasts.json';atomic_json(spec,[dict(family='E7',reference='fixed',treatment='adaptive_exact',metric='final_Y')])
            with patch('rsi_game.v04.plots.plot_family_statistics'):
                audit=build(root,out,metrics,spec)
            self.assertEqual(audit['valid_completed'],3);self.assertEqual(len(audit['missing_jobs']),1)
            self.assertEqual(len(list((out/'runs').glob('*.html'))),3)
            with (out/'all_arm_statistics.csv').open() as f:rows=list(csv.DictReader(f))
            result=next(r for r in rows if r['metric']=='final_Y')
            self.assertEqual(float(result['mean']),60) # (mean(10,30)+100)/2, not 140/3
            self.assertEqual(result['n'],'2')
            with (out/'planned_contrasts.csv').open() as f:contrast=next(csv.DictReader(f))
            self.assertEqual(contrast['n'],'0');self.assertIn('not estimable',contrast['status'])
            self.assertIn('PARTIAL', (out/'research_report.html').read_text())
            self.assertEqual(len(json.loads((out/'report_manifest.json').read_text())['source_files']),16)

    def test_mixed_model_versions_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'study'
            for seed in (0,1):
                job=dict(family='E7',arm='fixed',world_seed=0,seed=seed,world=dict(scenario='example1'),config=asdict(Config(periods=0,multistarts=2)))
                run_job(job,root)
                if seed:
                    p=job_path(root,job)/'manifest.json';d=json.loads(p.read_text());d['code_hash']='different';atomic_json(p,d)
            with self.assertRaisesRegex(ValueError,'Mixed model code hashes'):build(root,Path(tmp)/'report',metrics)
