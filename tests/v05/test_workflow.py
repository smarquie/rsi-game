import unittest,tempfile,json
from pathlib import Path
from dataclasses import asdict
from rsi_game.v05.config import Config
from rsi_game.v05.storage import run_job,atomic
from rsi_game.v05.research_report import report
from rsi_game.v05.experiments import plan
from rsi_game.v05.inference import paired_sign_test,holm

class WorkflowTests(unittest.TestCase):
    def test_integrity_resume_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=dict(id='0000000',family='test',arm='baseline',world_seed=100,seed=100,world=dict(archetype='saddle',seed=100),config=asdict(Config(periods=2,multistarts=4,access_starts=1)))
            atomic(Path(tmp)/'plan.json',dict(study='test',preset='smoke',jobs=[job]))
            self.assertEqual(run_job(job,tmp)['status'],'completed');self.assertEqual(run_job(job,tmp)['status'],'reused')
            output=report(tmp);self.assertTrue(output.exists());self.assertIn('COMPLETE',output.read_text());self.assertTrue((output.parent/'all_runs.csv').exists())
            result=Path(tmp)/'runs/0000000/result.json';result.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Integrity'):run_job(job,tmp)
    def test_partial_report_and_plan_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=plan('examples','smoke');atomic(Path(tmp)/'plan.json',p);out=report(tmp);self.assertIn('PARTIAL',out.read_text())
        with self.assertRaises(ValueError):plan('typology','paper',dict(selected=['R1','R3','R6'],preset='smoke'))
    def test_randomization_holm(self):
        self.assertEqual(paired_sign_test([1,1,1]),.25);self.assertIsNone(paired_sign_test([1]))
        rows=[dict(family='X',p_value=.01),dict(family='X',p_value=.04)];holm(rows);self.assertEqual(rows[0]['p_holm'],.02);self.assertEqual(rows[1]['p_holm'],.04)
    def test_plan_separation(self):
        p=plan('tuning','smoke');self.assertTrue(all(j['world_seed']<100 for j in p['jobs']))
        p=plan('core','smoke');self.assertTrue(all(j['world_seed']>=100 for j in p['jobs']));self.assertTrue(any(j.get('kind')=='independent' for j in p['jobs']))
