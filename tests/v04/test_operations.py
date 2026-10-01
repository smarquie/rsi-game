import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from rsi_game.v04.config import Config
from rsi_game.v04.world import make_world
from rsi_game.v04.experiments import plan
from rsi_game.v04.storage import run_job,job_path
from rsi_game.v04.analysis import interval

class Operations(unittest.TestCase):
    def test_resume_and_identity_guard(self):
        job=dict(family='test',arm='linear',world_seed=0,seed=0,world=dict(scenario='example1'),config=asdict(Config(periods=0,multistarts=2)))
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(run_job(job,root)['status'],'completed')
            folder=job_path(root,job)
            self.assertIsNone(json.loads((folder/'summary.json').read_text())['settling_period'])
            self.assertEqual(run_job(job,root)['status'],'reused')
            (folder/'complete.json').unlink()
            self.assertEqual(run_job(job,root)['status'],'completed')
            job['config']['beta']=.2
            with self.assertRaisesRegex(ValueError,'Existing run differs'):run_job(job,root)
    def test_replication_and_flags(self):
        d=plan('full',families=['E3'],worlds=2,replicates=4)
        self.assertEqual(d['job_count'],12)
        self.assertEqual(plan('full',families=['E3'],worlds=2,replicates=4,keep_duplicates=True)['job_count'],48)
        self.assertTrue(any('necessarily skip' in str(a['notes']) for a in plan('pilot',families=['E4'])['arms']))
    def test_interval_and_world_validation(self):
        self.assertIsNone(interval([1])['low'])
        self.assertEqual(interval([2,2,2])['high'],2.)
        with self.assertRaises(ValueError):Config(k=3).validate_world(make_world('example1'))
        with self.assertRaises(ValueError):Config(within_period='adaptive',budget_rule='ration')
