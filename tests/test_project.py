import csv
import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from hostel_cooling.domain import Action, Conditions, Preference, Room, legal_actions
from hostel_cooling.physics import step
from hostel_cooling.comfort import adaptive, fuzzy_vote
from hostel_cooling.optimizer import optimize, objective
from hostel_cooling.preferences import Memory, offline_patch
from hostel_cooling.llm import Offline, Ollama
from hostel_cooling.ann import ComfortANN
from hostel_cooling.policies import choose
from hostel_cooling.pilot import generate_pilot, load_pilot, calibrate


class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.r=Room(); self.c=Conditions(indoor_c=31,outdoor_c=27,solar_w_m2=600)

    def test_fan_adds_heat_but_improves_perceived_comfort(self):
        off,_=step(self.r,self.c,Action()); on,heat=step(self.r,self.c,Action(3))
        self.assertGreater(on.indoor_c,off.indoor_c)
        self.assertEqual(heat['fan_wh'],16.25)
        self.assertLess(abs(fuzzy_vote(on,self.r,Action(3),Preference())['tsv_proxy']),abs(fuzzy_vote(off,self.r,Action(),Preference())['tsv_proxy']))

    def test_shading_and_cool_ventilation_reduce_temperature(self):
        exposed,_=step(self.r,self.c,Action())
        shaded,_=step(self.r,self.c,Action(0,0,1))
        ventilated,_=step(self.r,self.c,Action(0,1,0))
        self.assertLess(shaded.indoor_c,exposed.indoor_c)
        self.assertLess(ventilated.indoor_c,exposed.indoor_c)

    def test_hot_outdoor_ventilation_can_heat_room(self):
        c=replace(self.c,outdoor_c=40,solar_w_m2=0)
        closed,_=step(self.r,c,Action());opened,_=step(self.r,c,Action(0,1))
        self.assertGreater(opened.indoor_c,closed.indoor_c)

    def test_analytic_integrator_time_consistency(self):
        c=replace(self.c,solar_w_m2=0,hour=16)
        one,_=step(self.r,c,Action(1),30)
        half,_=step(self.r,c,Action(1),15);two,_=step(self.r,half,Action(1),15)
        self.assertAlmostEqual(one.indoor_c,two.indoor_c,10)

    def test_adaptive_reference_known_value_and_sleep_exclusion(self):
        result=adaptive(replace(self.c,running_mean_c=20,indoor_c=25))
        self.assertAlmostEqual(result['neutral_c'],24)
        self.assertAlmostEqual(result['upper_80_c'],27.5)
        self.assertFalse(adaptive(replace(self.c,activity='sleep'))['applicable'])
        self.assertFalse(adaptive(replace(self.c,running_mean_c=40))['applicable'])

    def test_reject_non_finite_inputs(self):
        for v in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError): Conditions(indoor_c=v)
        with self.assertRaises(ValueError): Action(4)


class OptimizerTests(unittest.TestCase):
    def test_constraints_and_exact_gap(self):
        r,c,p=Room(),Conditions(activity='sleep',rain=True),Preference(sleep_max_fan=0)
        result=optimize(r,c,p)
        a=Action(**result['action'])
        self.assertEqual(a.fan,0);self.assertEqual(a.window,0)
        best=min(objective(r,c,p,x) for x in legal_actions(c,p))
        self.assertAlmostEqual(result['exact_gap'],result['objective']-best)
        self.assertTrue(all(a>=b for a,b in zip(result['ga_history'],result['ga_history'][1:])))

    def test_seed_reproducibility_and_away_fan(self):
        args=(Room(),Conditions(activity='away'),Preference())
        a,b=optimize(*args,seed=21),optimize(*args,seed=21)
        self.assertEqual(a,b);self.assertEqual(a['action']['fan'],0)

    def test_all_baselines_respect_window_and_sleep_constraints(self):
        r,c,p=Room(),Conditions(activity='sleep',poor_air=True),Preference(sleep_max_fan=0)
        ann=ComfortANN()
        for method in ('fixed','expert','adaptive','ann','physics','memoryless','ours','survey'):
            action,_=choose(method,r,c,p,Action(),ann,Offline())
            self.assertEqual(action.fan,0,method);self.assertEqual(action.window,0,method)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.m=Memory(Path(self.temp.name)/'test.db')

    def tearDown(self): self.temp.cleanup()

    def test_consent_required_and_persistence(self):
        with self.assertRaises(PermissionError): self.m.update('p','I prefer 27 C','study',Offline())
        self.m.consent('p',True)
        self.m.update('p','I prefer 27 C. I want airflow.','study',Offline())
        self.m.update('p','I prefer 29 C. I need quiet when sleeping.','sleep',Offline())
        fresh=Memory(self.m.path).profile('p')
        self.assertEqual(fresh['preference']['activity_targets'],{'study':27.,'sleep':29.})
        self.assertTrue(fresh['preference']['study_airflow'])
        self.assertEqual(len(fresh['events']),2)

    def test_invalid_llm_patch_does_not_corrupt_memory(self):
        class Bad:
            name='bad';extract=lambda *args:{'sleep_max_fan':99}
        self.m.consent('p',True)
        with self.assertRaises(ValueError):self.m.update('p','hello','study',Bad())
        self.assertEqual(self.m.profile('p')['events'],[])
        self.assertEqual(self.m.profile('p')['preference']['sleep_max_fan'],1)

    def test_erasure_covers_suggestions_and_votes(self):
        self.m.consent('p',True)
        sid=self.m.save_suggestion('p',{'test':1})
        self.m.feedback('p',sid,True,0)
        self.m.consent('p',False)
        exported=self.m.export('p')
        self.assertFalse(exported['consent']);self.assertEqual(exported['suggestions'],[]);self.assertEqual(exported['feedback'],[])

    def test_feedback_must_reference_owned_suggestion(self):
        self.m.consent('p',True);sid=self.m.save_suggestion('p',{})
        with self.assertRaises(ValueError):self.m.feedback('other',sid,True,0)

    def test_negation_and_unsupported_message(self):
        p=Preference()
        self.assertEqual(offline_patch('I am not too hot','study',p),{})
        self.assertEqual(offline_patch("I don't prefer 27 C",'study',p),{})
        self.assertEqual(offline_patch('Please do not infer my age','study',p),{})
        self.assertFalse(offline_patch('I do not want airflow','study',p)['study_airflow'])

    def test_ollama_schema_validation_without_network(self):
        llm=Ollama(model='fixture')
        llm.chat=lambda *args:{'target_c':99}
        with self.assertRaises(ValueError):llm.extract('message','study',Preference())
        llm.chat=lambda *args:{'fan':3,'window':1,'curtain':0}
        with self.assertRaises(ValueError):llm.generic_action(Conditions(rain=True),[Action()])


class DataTests(unittest.TestCase):
    def test_ann_has_real_training_and_independent_holdout(self):
        ann=ComfortANN()
        self.assertEqual(ann.validation['train_n'],2000)
        self.assertLess(ann.validation['mae_tsv'],.3)

    def test_csv_validation_calibration_and_invalid_consent(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pilot.csv';generate_pilot(path,days=1)
            rows=load_pilot(path);self.assertEqual(len(rows),96)
            result=calibrate(path,Path(folder)/'fit.json')
            self.assertLess(result['test_rmse_c'],1e-8)
            self.assertEqual(result['selected_room']['capacity_j_k'],2_000_000)
            text=path.read_text();path.write_text(text.replace(',true,synthetic',',false,synthetic',1))
            with self.assertRaisesRegex(ValueError,'consent'):load_pilot(path)

    def test_csv_gaps_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pilot.csv';generate_pilot(path,days=1)
            lines=path.read_text().splitlines();del lines[4];path.write_text('\n'.join(lines))
            with self.assertRaisesRegex(ValueError,'15-minute'):load_pilot(path)


if __name__=='__main__':unittest.main()
