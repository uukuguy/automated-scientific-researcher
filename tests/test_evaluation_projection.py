"""Conservative evaluator projection semantics; no model or container calls."""
import importlib
import importlib.util
import json
import unittest
from unittest.mock import patch


class EvaluationProjectionTests(unittest.TestCase):
    def module(self):
        name='integrations.aar.evaluation_projection'
        self.assertIsNotNone(importlib.util.find_spec(name),'trusted conservative projection required')
        return importlib.import_module(name)

    def job(self):
        return dict(settled=True,evaluation_id='eval',evaluation_attempt_id='eval-attempt',
                    target={'trial_id':'trial'},artifact={'sha256':'a'*64},
                    report={'result':dict(input_preserved=True,equation_valid=True,
                        operational_status='violated',thermal_limits_unassessed=186,max_mismatch_pu=1e-10)})

    def test_valid_equations_do_not_imply_valid_design_hypothesis_or_generalization(self):
        document=self.module().validation_document(self.job())
        axes=document['assessments']
        self.assertEqual(axes['equation_validity'],'valid')
        self.assertEqual(axes['operating_checks'],'violated')
        for axis in ('experiment_validity','hypothesis_assessment','generalization','replication'):
            self.assertEqual(axes[axis],'unassessed')
        self.assertEqual(document['evaluation_artifact'],dict(evaluation_id='eval',
            evaluation_attempt_id='eval-attempt',artifact_sha256='a'*64))

    def test_changed_original_input_is_invalid_without_becoming_hypothesis_refutation(self):
        job=self.job();job['report']['result'].update(input_preserved=False,equation_valid=False)
        axes=self.module().validation_document(job)['assessments']
        self.assertEqual(axes['experiment_validity'],'invalid')
        self.assertEqual(axes['equation_validity'],'invalid')
        self.assertEqual(axes['hypothesis_assessment'],'unassessed')

    def test_failed_evaluator_does_not_invent_numerical_assessment(self):
        job=self.job();job['report']['result']=None
        axes=self.module().validation_document(job)['assessments']
        self.assertEqual(axes['equation_validity'],'unassessed')
        self.assertEqual(axes['operating_checks'],'unassessed')

    def test_unsettled_job_cannot_be_projected(self):
        module=self.module();job=self.job();job['settled']=False
        with self.assertRaisesRegex(ValueError,'settled_evaluation_required'):
            module.validation_document(job)

    def comparison_fixture(self):
        def trial(identifier,container):
            return dict(trial_id=identifier,execution_attempt_id=identifier+'-attempt',research_run_id='run',
                references={'evaluation':'evaluation-ref'},dispatch_state='succeeded',
                execution=dict(identity={'container_id':container},report=dict(execution_exited=True,
                    evidence_path='/trusted/'+identifier,manifest_hash=identifier+'-manifest')))
        source=trial('source','container-1');replica=trial('replica','container-2')
        replica['replicates']={'trial_id':'source'}
        def job(trial):
            return dict(settled=True,evaluation_id='eval-'+trial['trial_id'],artifact={'sha256':'a'*64},
                target=dict(trial_id=trial['trial_id'],execution_attempt_id=trial['execution_attempt_id'],
                    manifest_hash=trial['execution']['report']['manifest_hash'],evaluation_ref='evaluation-ref'),
                report=dict(execution_status='succeeded',result={'equation_valid':False}))
        frozen=dict(input_sha256='same-input',solution_sha256='same-solution',
            files={'request.json':json.dumps(dict(profile='octave-candidate/1',candidate={'sha256':'same-code'})).encode()})
        return source,replica,job(source),job(replica),frozen

    def test_exact_method_replay_requires_both_independent_evaluations(self):
        module=self.module()
        self.assertTrue(callable(getattr(module,'compare_replication',None)))
        source,replica,first,second,frozen=self.comparison_fixture()
        with patch('asr_evaluation.replay.freeze_source',return_value=frozen) as verify:
            result=module.compare_replication(source,replica,first,second)
        self.assertEqual(result['status'],'consistent')
        self.assertEqual(verify.call_count,2)
        second['report']['execution_status']='failed'
        with self.assertRaisesRegex(ValueError,'successful_independent_evaluations_required'):
            module.compare_replication(source,replica,first,second)

    def test_same_container_or_changed_code_cannot_count_as_replication(self):
        module=self.module()
        self.assertTrue(callable(getattr(module,'compare_replication',None)))
        source,replica,first,second,frozen=self.comparison_fixture()
        replica['execution']['identity']['container_id']='container-1'
        with patch('asr_evaluation.replay.freeze_source',return_value=frozen):
            with self.assertRaisesRegex(ValueError,'replication_identity_mismatch'):
                module.compare_replication(source,replica,first,second)

    def test_bytewise_difference_is_explicit_policy_inconsistency(self):
        module=self.module()
        self.assertTrue(callable(getattr(module,'compare_replication',None)))
        source,replica,first,second,frozen=self.comparison_fixture()
        changed=dict(frozen,solution_sha256='different-solution')
        with patch('asr_evaluation.replay.freeze_source',side_effect=[frozen,changed]):
            result=module.compare_replication(source,replica,first,second)
        self.assertEqual(result['status'],'inconsistent')
        self.assertEqual(result['protocol'],'exact-frozen-solution/1')


if __name__=='__main__':unittest.main()
