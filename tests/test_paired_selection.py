"""Frozen team selection rules, synthetic metric fixtures only."""
import copy
import unittest


def fixture():
    roster={'baseline':'baseline','arms':{a:{str(s):f'{a}-{s}' for s in range(1101,1109)} for a in ('TT','BT','TG','BG')}}
    metrics={v:dict(id_rmse=.00002,target_rmse=.7) for arm in roster['arms'].values() for v in arm.values()}
    metrics['baseline']=dict(id_rmse=.00002,target_rmse=1.)
    panels={name:dict(proposed=256,valid=256) for name in ('id','target')}
    return roster,metrics,panels


class PairedSelectionTests(unittest.TestCase):
    def setUp(self):self.roster,self.metrics,self.panels=fixture()

    def select(self):
        from paired_selection_reference import select_development
        return select_development(self.roster,self.metrics,self.panels)

    def test_all_33_models_and_all_eight_seeds_required(self):
        self.metrics.pop('TT-1101')
        with self.assertRaisesRegex(ValueError,'complete frozen'):self.select()

    def test_arm_requires_seven_passes_and_uses_all_eight_for_median(self):
        for a in self.roster['arms']:
            for trial in self.roster['arms'][a].values():self.metrics[trial]['target_rmse']=.9
        for seed in range(1101,1108):self.metrics[f'TT-{seed}']['target_rmse']=.6
        for seed in range(1101,1107):self.metrics[f'BG-{seed}']['target_rmse']=.1
        result=self.select();self.assertEqual(result['selected_arm'],'TT');self.assertEqual(result['primary_model'],'TT-1101')
        self.assertEqual(result['arms']['BG']['passing_seeds'],6)
        self.assertAlmostEqual(result['arms']['TT']['median_target_rmse'],.6)

    def test_ties_use_arm_name_then_numeric_seed_and_id_degradation_retained(self):
        self.metrics['BG-1101']['id_rmse']=.00003
        result=self.select();self.assertEqual(result['primary_model'],'BG-1101')
        self.assertAlmostEqual(result['models']['BG-1101']['id_rmse_ratio'],1.5)
        self.assertTrue(result['models']['BG-1101']['joint_pass'])

    def test_no_eligible_arm_falls_back_and_cannot_claim_improvement(self):
        for v in self.metrics.values():v['target_rmse']=1.
        result=self.select();self.assertEqual(result['primary_model'],'baseline');self.assertEqual(result['assessment'],'development_objective_unmet')

    def test_below_95_percent_yield_withholds_selection_at_exact_boundary(self):
        self.panels['id']['valid']=243
        result=self.select();self.assertIsNone(result['primary_model']);self.assertEqual(result['assessment'],'label_yield_failure')
        self.panels['id']['valid']=244
        self.assertIsNotNone(self.select()['primary_model'])

    def test_nonfinite_negative_incomplete_or_duplicate_model_assignments_rejected(self):
        for invalid in (float('nan'),float('inf'),-.1,True):
            self.metrics['TT-1101']['target_rmse']=invalid
            with self.assertRaises(ValueError):self.select()
        self.metrics['TT-1101']['target_rmse']=.7
        self.roster['arms']['TT']['1101']='baseline'
        with self.assertRaises(ValueError):self.select()

    def test_zero_baseline_retains_literal_predicate_without_inventing_ratio(self):
        for v in self.metrics.values():v['target_rmse']=0.
        result=self.select();self.assertIsNone(result['models']['TT-1101']['target_rmse_ratio'])
        self.assertTrue(result['models']['TT-1101']['joint_pass'])

    def test_final_cannot_reselect_a_better_alternative_or_accept_fallback(self):
        from paired_selection_reference import confirm_final, digest
        selected=self.select();metrics=copy.deepcopy(self.metrics)
        metrics[selected['primary_model']]['target_rmse']=.95
        metrics['TT-1108']['target_rmse']=.01
        panels={name:dict(proposed=512,valid=512) for name in ('id','target')}
        final=confirm_final(self.roster,metrics,panels,selected,expected_selection_sha256=digest(selected))
        self.assertEqual(final['primary_model'],selected['primary_model']);self.assertEqual(final['assessment'],'final_objective_unmet')
        for v in self.metrics.values():v['target_rmse']=1.
        fallback=self.select()
        final=confirm_final(self.roster,metrics,panels,fallback,expected_selection_sha256=digest(fallback))
        self.assertEqual(final['assessment'],'final_objective_unmet')

    def test_final_selection_pin_and_roster_are_frozen(self):
        from paired_selection_reference import confirm_final, digest
        selection=self.select();pin=digest(selection);selection['primary_model']='TT-1108'
        panels={name:dict(proposed=512,valid=512) for name in ('id','target')}
        with self.assertRaisesRegex(ValueError,'selection pin'):
            confirm_final(self.roster,self.metrics,panels,selection,expected_selection_sha256=pin)
